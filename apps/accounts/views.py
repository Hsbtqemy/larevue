import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        return render(request, self.template_name, {
            "patch_url": reverse("accounts:profile_patch"),
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
