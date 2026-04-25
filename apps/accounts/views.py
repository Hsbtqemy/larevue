import json

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.accounts.forms import ProfilePasswordForm
from apps.issues.models import Issue


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
            user.full_clean()
            user.save(update_fields=[field])
        except ValidationError as e:
            return JsonResponse({"error": " ".join(e.messages)}, status=400)

        return JsonResponse({"ok": True})


class ProfilePasswordView(LoginRequiredMixin, View):
    def post(self, request):
        form = ProfilePasswordForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            return redirect(reverse("accounts:profile") + "?pw=ok")
        return render(request, "accounts/profile.html", {
            "patch_url": reverse("accounts:profile_patch"),
            "pw_form": form,
            "pw_open": True,
            "memberships": _memberships_for(request.user),
        })
