from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.administration.forms import (
    JournalCreateAdminForm,
    UserCreateForm,
    UserEditForm,
    UserQuickCreateForm,
)
from apps.core.mixins import SuperuserRequiredMixin
from apps.core.utils import generate_temp_password
from apps.issues.models import Issue
from apps.journals.models import Journal, Membership

User = get_user_model()


def _form_errors(form):
    return {field: list(errs) for field, errs in form.errors.items()}


class AdministrationView(SuperuserRequiredMixin, View):
    template_name = "administration/index.html"

    def get(self, request):
        archived_states = [s.value for s in Issue.ARCHIVED_STATES]
        journals = (
            Journal.objects.annotate(
                member_count=Count("memberships", distinct=True),
                issue_count=Count("issues", distinct=True),
                active_issue_count=Count(
                    "issues",
                    filter=~Q(issues__state__in=archived_states),
                    distinct=True,
                ),
            )
            .order_by("name")
        )
        users = (
            User.objects.annotate(journal_count=Count("memberships", distinct=True))
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=Membership.objects.select_related("journal").order_by("journal__name"),
                    to_attr="memberships_preview",
                )
            )
            .order_by("last_name", "first_name", "email")
        )
        first = request.user.memberships.select_related("journal").first()
        return render(request, self.template_name, {
            "journals": journals,
            "users": users,
            "accent_choices": Journal.ACCENT_CHOICES,
            "journal_form": JournalCreateAdminForm(),
            "user_form": UserCreateForm(),
            "user_search_url": reverse("administration:user_search"),
            "journal": first.journal if first else None,
        })


class JournalCreateView(SuperuserRequiredMixin, View):
    def post(self, request):
        form = JournalCreateAdminForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                journal = form.save()
                Membership.objects.create(user=request.user, journal=journal)
            return JsonResponse({
                "redirect_url": reverse(
                    "administration:journal_members",
                    kwargs={"slug": journal.slug},
                )
            })
        return JsonResponse({"errors": _form_errors(form)}, status=400)


class UserSearchView(SuperuserRequiredMixin, View):
    """Return users matching a query, optionally excluding members of a journal."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        exclude_journal_slug = request.GET.get("exclude_journal", "")

        users = User.objects.all()
        if q:
            users = users.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        if exclude_journal_slug:
            users = users.exclude(memberships__journal__slug=exclude_journal_slug)

        results = [
            {"id": u.pk, "name": u.get_full_name() or u.email, "email": u.email}
            for u in users.order_by("last_name", "first_name")[:10]
        ]
        return JsonResponse({"results": results})


class UserCreateView(SuperuserRequiredMixin, View):
    def post(self, request):
        form = UserCreateForm(request.POST)
        if form.is_valid():
            journal_ids = request.POST.getlist("journal_ids")
            with transaction.atomic():
                password = generate_temp_password()
                user = form.save(commit=False)
                user.set_password(password)
                user.must_change_password = True
                user.save()
                if journal_ids:
                    journals = Journal.objects.filter(pk__in=journal_ids)
                    Membership.objects.bulk_create(
                        [Membership(user=user, journal=j) for j in journals],
                        ignore_conflicts=True,
                    )
            request.session["temp_password"] = password
            request.session["temp_password_user_id"] = user.pk
            return JsonResponse({
                "redirect_url": reverse(
                    "administration:user_password_display",
                    kwargs={"user_id": user.pk},
                )
            })
        return JsonResponse({"errors": _form_errors(form)}, status=400)


class UserPasswordDisplayView(SuperuserRequiredMixin, View):
    """Show the temporary password once and delete it from the session immediately."""

    template_name = "administration/user_password_display.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        password = request.session.pop("temp_password", None)
        stored_uid = request.session.pop("temp_password_user_id", None)
        # Guard against accessing this URL without going through the creation flow.
        if password is None or stored_uid != user.pk:
            return redirect(reverse("administration:index"))
        first = request.user.memberships.select_related("journal").first()
        return render(request, self.template_name, {
            "created_user": user,
            "temp_password": password,
            "journal": first.journal if first else None,
        })


class UserDetailView(SuperuserRequiredMixin, View):
    template_name = "administration/user_detail.html"

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        memberships = user.memberships.select_related("journal").order_by("journal__name")
        member_journal_ids = memberships.values_list("journal_id", flat=True)
        available_journals = Journal.objects.exclude(pk__in=member_journal_ids).order_by("name")
        first = request.user.memberships.select_related("journal").first()
        return render(request, self.template_name, {
            "target_user": user,
            "memberships": memberships,
            "available_journals": available_journals,
            "journal": first.journal if first else None,
        })


class UserResetPasswordView(SuperuserRequiredMixin, View):
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        password = generate_temp_password()
        user.set_password(password)
        user.must_change_password = True
        user.save()
        request.session["temp_password"] = password
        request.session["temp_password_user_id"] = user.pk
        return redirect(
            reverse("administration:user_password_display", kwargs={"user_id": user.pk})
        )


class UserAddJournalView(SuperuserRequiredMixin, View):
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        journal_id = request.POST.get("journal_id", "").strip()
        journal = get_object_or_404(Journal, pk=journal_id)
        Membership.objects.get_or_create(user=user, journal=journal)
        return redirect(reverse("administration:user_detail", kwargs={"user_id": user.pk}))


class UserRemoveJournalView(SuperuserRequiredMixin, View):
    def delete(self, request, user_id, slug):
        user = get_object_or_404(User, pk=user_id)
        journal = get_object_or_404(Journal, slug=slug)
        Membership.objects.filter(user=user, journal=journal).delete()
        return JsonResponse({
            "redirect_url": reverse("administration:user_detail", kwargs={"user_id": user.pk})
        })


class UserEditView(SuperuserRequiredMixin, View):
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        form = UserEditForm(user, request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": _form_errors(form)}, status=400)

        # Prevent a superuser from revoking their own superuser flag.
        if user.pk == request.user.pk and not form.cleaned_data["is_superuser"]:
            return JsonResponse(
                {"errors": {"is_superuser": [
                    "Vous ne pouvez pas révoquer vos propres droits superuser. "
                    "Demandez à un autre superuser de le faire."
                ]}},
                status=400,
            )

        form.save()
        return JsonResponse({"ok": True})


class JournalMembersView(SuperuserRequiredMixin, View):
    template_name = "administration/journal_members.html"

    def get(self, request, slug):
        journal = get_object_or_404(Journal, slug=slug)
        memberships = journal.memberships.select_related("user").order_by(
            "user__last_name", "user__first_name"
        )
        archived_states = [s.value for s in Issue.ARCHIVED_STATES]
        issues = journal.issues.all()
        return render(request, self.template_name, {
            "journal": journal,
            "memberships": memberships,
            "active_issue_count": issues.exclude(state__in=archived_states).count(),
            "published_issue_count": issues.filter(state=Issue.State.PUBLISHED).count(),
            "archived_issue_count": issues.filter(state__in=archived_states).count(),
            "user_search_url": reverse("administration:user_search"),
            "member_add_url": reverse(
                "administration:journal_member_add", kwargs={"slug": slug}
            ),
            "journal_edit_url": reverse("journal_edit", kwargs={"slug": slug}),
            "quick_create_url": reverse(
                "administration:journal_member_quick_create", kwargs={"slug": slug}
            ),
        })


class JournalMemberAddView(SuperuserRequiredMixin, View):
    def post(self, request, slug):
        journal = get_object_or_404(Journal, slug=slug)
        user_id = request.POST.get("user_id", "").strip()
        if not user_id:
            return JsonResponse({"error": "Utilisateur·ice requis."}, status=400)
        user = get_object_or_404(User, pk=user_id)
        _, created = Membership.objects.get_or_create(user=user, journal=journal)
        if not created:
            return JsonResponse({"error": "Cet·te utilisateur·ice est déjà membre."}, status=400)
        return JsonResponse({"ok": True})


class JournalMemberRemoveView(SuperuserRequiredMixin, View):
    def delete(self, request, slug, user_id):
        journal = get_object_or_404(Journal, slug=slug)
        user = get_object_or_404(User, pk=user_id)
        Membership.objects.filter(user=user, journal=journal).delete()
        return JsonResponse({
            "redirect_url": reverse("administration:journal_members", kwargs={"slug": slug})
        })


class JournalMemberQuickCreateView(SuperuserRequiredMixin, View):
    """Create a new user account and immediately add them to the journal."""

    def post(self, request, slug):
        journal = get_object_or_404(Journal, slug=slug)
        form = UserQuickCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                password = generate_temp_password()
                user = form.save(commit=False)
                user.set_password(password)
                user.must_change_password = True
                user.save()
                Membership.objects.create(user=user, journal=journal)
            request.session["temp_password"] = password
            request.session["temp_password_user_id"] = user.pk
            return JsonResponse({
                "redirect_url": reverse(
                    "administration:user_password_display",
                    kwargs={"user_id": user.pk},
                )
            })
        return JsonResponse({"errors": _form_errors(form)}, status=400)


class UserToggleActiveView(SuperuserRequiredMixin, View):
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        return JsonResponse({"ok": True, "is_active": user.is_active})


class JournalDeleteView(SuperuserRequiredMixin, View):
    def delete(self, request, slug):
        journal = get_object_or_404(Journal, slug=slug)
        journal.delete()
        return JsonResponse({"redirect_url": reverse("administration:index")})
