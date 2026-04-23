import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views import View

from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin


class JournalOwnedPatchView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):

    ALLOWED_FIELDS: set = set()
    AUDIT_FIELDS: set = set()
    FULL_CLEAN_EXCLUDE: list = []

    def check_editable(self, obj):
        return None

    def get_allowed_fields(self, obj):
        return self.ALLOWED_FIELDS

    def resolve_field_value(self, field_name, raw_value, field_obj):
        if field_obj.null and raw_value == "":
            return None
        return raw_value

    def create_audit_note(self, obj, field_name, old_value, new_value, field_obj):
        pass

    def post(self, request, **kwargs):
        obj = self.get_object_or_404()

        guard = self.check_editable(obj)
        if guard:
            return guard

        try:
            data = json.loads(request.body)
            field_name = data["field"]
            raw_value = data.get("value", "")
        except (json.JSONDecodeError, KeyError, TypeError):
            return JsonResponse({"error": "Requête invalide."}, status=400)

        if field_name not in self.get_allowed_fields(obj):
            return JsonResponse({"error": "Champ non modifiable."}, status=400)

        field_obj = obj._meta.get_field(field_name)
        old_value = getattr(obj, field_name)

        try:
            new_value = self.resolve_field_value(field_name, raw_value, field_obj)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

        setattr(obj, field_name, new_value)

        try:
            obj.full_clean(exclude=self.FULL_CLEAN_EXCLUDE)
            obj.save(update_fields=[field_obj.attname])
        except ValidationError as e:
            return JsonResponse({"error": " ".join(e.messages)}, status=400)

        if field_name in self.AUDIT_FIELDS:
            self.create_audit_note(obj, field_name, old_value, new_value, field_obj)

        return JsonResponse({"ok": True})
