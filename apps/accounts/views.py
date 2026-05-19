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
from django.utils import timezone
from django.views import View

from apps.accounts.forms import ProfilePasswordForm, ReviewerActivateForm, ReviewerInviteForm, ReviewerSubmitForm
from apps.accounts.tokens import load_invitation_token, make_invitation_token
from apps.contacts.models import Contact
from apps.core.mail import send_review_received_editors, send_review_received_reviewer, send_reviewer_added, send_reviewer_invitation
from apps.core.mixins import JournalMemberRequiredMixin
from apps.issues.models import Issue
from apps.reviews.models import ReviewRequest

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


def _ensure_contact(journal, email, first_name, last_name, user):
    contact = Contact.objects.filter(email=email, journal=journal).first()
    if not contact:
        Contact.objects.create(
            journal=journal, email=email,
            first_name=first_name, last_name=last_name, user=user,
        )
    elif contact.user_id is None:
        contact.user = user
        contact.save(update_fields=["user"])


def _reviews_for(user):
    active_states = {ReviewRequest.State.ASSIGNED, ReviewRequest.State.SENT}
    all_reviews = list(
        ReviewRequest.objects.filter(reviewer__user=user)
        .select_related("article", "article__issue", "article__issue__journal", "article_version")
        .order_by("deadline")
    )
    return (
        [r for r in all_reviews if r.state in active_states],
        [r for r in all_reviews if r.state not in active_states],
    )


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        reviews_active, reviews_done = _reviews_for(request.user)
        return render(request, self.template_name, {
            "patch_url": reverse("accounts:profile_patch"),
            "pw_form": ProfilePasswordForm(request.user),
            "pw_success": request.GET.get("pw") == "ok",
            "memberships": _memberships_for(request.user),
            "reviews_active": reviews_active,
            "reviews_done": reviews_done,
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
    def _ctx(self, request, **extra):
        reviews_active, reviews_done = _reviews_for(request.user)
        return {
            "patch_url": reverse("accounts:profile_patch"),
            "memberships": _memberships_for(request.user),
            "reviews_active": reviews_active,
            "reviews_done": reviews_done,
            **extra,
        }

    def get(self, request):
        return render(request, ProfileView.template_name,
                      self._ctx(request, pw_form=ProfilePasswordForm(request.user), pw_open=True))

    def post(self, request):
        form = ProfilePasswordForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.must_change_password = False
            request.user.save()
            update_session_auth_hash(request, request.user)
            return redirect(reverse("accounts:profile") + "?pw=ok")
        return render(request, ProfileView.template_name,
                      self._ctx(request, pw_form=form, pw_open=True))


class ReviewerInviteView(JournalMemberRequiredMixin, View):
    template_name = "accounts/reviewer_invite.html"

    def get(self, request, slug):
        contact_search_url = reverse("contacts:search", kwargs={"slug": slug})
        return render(request, self.template_name, {
            "form": ReviewerInviteForm(),
            "contact_search_url": contact_search_url,
        })

    def post(self, request, slug):
        form = ReviewerInviteForm(request.POST)
        contact_search_url = reverse("contacts:search", kwargs={"slug": slug})
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "contact_search_url": contact_search_url})

        email = form.cleaned_data["email"]
        first_name = form.cleaned_data["first_name"]
        last_name = form.cleaned_data["last_name"]
        existing = User.objects.filter(email=email).first()

        if existing and existing.is_active:
            if existing.is_reviewer:
                form.add_error("email", "Ce relecteur possède déjà un compte actif.")
                return render(request, self.template_name, {"form": form, "contact_search_url": contact_search_url})
            _ensure_contact(request.journal, email, first_name, last_name, existing)
            send_reviewer_added(
                email=email,
                reviewer_name=existing.get_full_name() or email,
                journal_name=request.journal.name,
                profile_url=request.build_absolute_uri(reverse("accounts:profile")),
                journal=request.journal,
            )
            messages.success(request, f"{existing.get_full_name() or email} a déjà un compte Edito. Une notification lui a été envoyée.")
            return redirect(request.path)

        if existing:
            user = existing
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=["first_name", "last_name"])
        else:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_reviewer=True,
                is_active=False,
            )
            user.set_unusable_password()
            user.save()

        _ensure_contact(request.journal, email, first_name, last_name, user)

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
        active_reviews, done_reviews = _reviews_for(request.user)
        return render(request, self.template_name, {
            "active_reviews": active_reviews,
            "done_reviews": done_reviews,
        })


class ReviewerReviewSubmitView(LoginRequiredMixin, View):
    template_name = "accounts/reviewer_review_submit.html"

    def _get_review(self, request, pk):
        try:
            review = ReviewRequest.objects.select_related(
                "article", "article__issue", "article__issue__journal",
                "article_version", "reviewer",
            ).get(pk=pk)
        except ReviewRequest.DoesNotExist:
            return None
        if review.reviewer_id is None or review.reviewer.user_id != request.user.pk:
            return None
        if review.state != ReviewRequest.State.SENT:
            return None
        return review

    def get(self, request, pk):
        review = self._get_review(request, pk)
        if review is None:
            return redirect("accounts:reviewer_dashboard")
        return render(request, self.template_name, {
            "review": review,
            "form": ReviewerSubmitForm(),
        })

    def post(self, request, pk):
        review = self._get_review(request, pk)
        if review is None:
            return redirect("accounts:reviewer_dashboard")
        form = ReviewerSubmitForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"review": review, "form": form})
        review.received_file = form.cleaned_data["received_file"]
        review.verdict = form.cleaned_data["verdict"]
        review.state = ReviewRequest.State.RECEIVED
        review.received_at = timezone.now()
        review.save(update_fields=["received_file", "verdict", "state", "received_at"])
        send_review_received_reviewer(review)
        send_review_received_editors(review)
        messages.success(request, "Votre relecture a bien été déposée. Merci !")
        return redirect("accounts:reviewer_dashboard")
