import json

from django.contrib import messages
from django.contrib.auth import get_user_model, login, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.accounts.forms import ProfilePasswordForm, ReviewerActivateForm, ReviewerInviteForm
from apps.accounts.tokens import load_invitation_token, make_invitation_token
from apps.core.mail import send_reviewer_invitation
from apps.core.mixins import JournalMemberRequiredMixin
from apps.issues.models import Issue

User = get_user_model()


def _memberships_for(user):
    return list(
        user.memberships
        .select_related("journal")
        .annotate(
            active_issue_count=Count(
                "journal__issues",
                filter=~Q(journal__issues__state__in=Issue.ARCHIVED_STATES),
                distinct=True,
            ),
            member_count=Count("journal__memberships", distinct=True),
        )
    )


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        return render(request, self.template_name, {
            "patch_url": reverse("accounts:profile_patch"),
            "pw_form": ProfilePasswordForm(request.user),
            "pw_success": request.GET.get("pw") == "ok",
            "memberships": _memberships_for(request.user),
        })


class ProfilePatchView(LoginRequiredMixin, View):
    ALLOWED_FIELDS = {"first_name", "last_name", "email"}

    def post(self, request):
        try:
            data = json.loads(request.body)
            field = data["field"]
            value = str(data.get("value", "")).strip()
        except (json.JSONDecodeError, KeyError, TypeError):
            return JsonResponse({"error": "Requête invalide."}, status=400)

        if field not in self.ALLOWED_FIELDS:
            return JsonResponse({"error": "Champ non modifiable."}, status=400)

        user = request.user
        setattr(user, field, value)
        try:
            # Validate only the field being patched; skip the other allowed fields
            # which may legitimately be empty (e.g. last_name="" on a fresh account).
            user.full_clean(exclude=[f for f in self.ALLOWED_FIELDS if f != field])
            user.save(update_fields=[field])
        except ValidationError as e:
            return JsonResponse({"error": " ".join(e.messages)}, status=400)

        return JsonResponse({"ok": True})


class ProfilePasswordView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, ProfileView.template_name, {
            "patch_url": reverse("accounts:profile_patch"),
            "pw_form": ProfilePasswordForm(request.user),
            "pw_open": True,
            "memberships": _memberships_for(request.user),
        })

    def post(self, request):
        form = ProfilePasswordForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.must_change_password = False
            request.user.save()
            update_session_auth_hash(request, request.user)
            return redirect(reverse("accounts:profile") + "?pw=ok")
        return render(request, ProfileView.template_name, {
            "patch_url": reverse("accounts:profile_patch"),
            "pw_form": form,
            "pw_open": True,
            "memberships": _memberships_for(request.user),
        })


class ReviewerInviteView(JournalMemberRequiredMixin, View):
    template_name = "accounts/reviewer_invite.html"

    def get(self, request, slug):
        return render(request, self.template_name, {"form": ReviewerInviteForm()})

    def post(self, request, slug):
        form = ReviewerInviteForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        email = form.cleaned_data["email"]
        existing = User.objects.filter(email=email).first()

        if existing and existing.is_active and not existing.is_reviewer:
            form.add_error("email", "Cette adresse appartient déjà à un compte éditeur.")
            return render(request, self.template_name, {"form": form})

        if existing and existing.is_active:
            form.add_error("email", "Ce relecteur possède déjà un compte actif.")
            return render(request, self.template_name, {"form": form})

        if existing:
            user = existing
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.save(update_fields=["first_name", "last_name"])
        else:
            user = User(
                email=email,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                is_reviewer=True,
                is_active=False,
            )
            user.set_unusable_password()
            user.save()

        # Lier au Contact si l'email correspond
        from apps.contacts.models import Contact
        contact = Contact.objects.filter(email=email, journal=request.journal).first()
        if contact and contact.user_id is None:
            contact.user = user
            contact.save(update_fields=["user"])

        token = make_invitation_token(user.pk)
        activation_url = request.build_absolute_uri(
            reverse("accounts:reviewer_activate", kwargs={"token": token})
        )
        send_reviewer_invitation(
            email=email,
            reviewer_name=user.get_full_name() or email,
            journal_name=request.journal.name,
            activation_url=activation_url,
        )
        messages.success(request, f"Invitation envoyée à {email}.")
        return redirect(request.path)


class ReviewerActivateView(View):
    template_name = "accounts/reviewer_activate.html"

    def _resolve(self, token):
        try:
            user_pk = load_invitation_token(token)
            return User.objects.get(pk=user_pk, is_reviewer=True)
        except (signing.SignatureExpired, signing.BadSignature, User.DoesNotExist):
            return None

    def get(self, request, token):
        user = self._resolve(token)
        if user is None:
            return render(request, self.template_name, {"expired": True})
        if user.is_active:
            return redirect("account_login")
        return render(request, self.template_name, {"form": ReviewerActivateForm(), "token": token})

    def post(self, request, token):
        user = self._resolve(token)
        if user is None:
            return render(request, self.template_name, {"expired": True})
        if user.is_active:
            return redirect("account_login")
        form = ReviewerActivateForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "token": token})
        user.set_password(form.cleaned_data["password"])
        user.is_active = True
        user.must_change_password = False
        user.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("accounts:reviewer_dashboard")


class ReviewerDashboardView(LoginRequiredMixin, View):
    template_name = "accounts/reviewer_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_reviewer:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from apps.reviews.models import ReviewRequest
        reviews = ReviewRequest.objects.filter(
            reviewer__user=request.user
        ).select_related("article", "article__issue", "article__issue__journal")
        return render(request, self.template_name, {"reviews": reviews})
