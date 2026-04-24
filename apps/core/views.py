import json

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views import View
from django_fsm import can_proceed

from apps.core.mixins import JournalMemberRequiredMixin, JournalOwnedObjectMixin


def compute_transitions(specs, obj, is_archived=False):
    if is_archived:
        return {"primary": None, "secondary": [], "advanced": []}
    primary = None
    secondary = []
    advanced = []
    for name, spec in specs.items():
        if not can_proceed(getattr(obj, name)):
            continue
        enabled = True
        disabled_reason = ""
        if precondition := spec.get("precondition"):
            ok, msg = precondition(obj)
            if not ok:
                enabled = False
                disabled_reason = msg
        description = spec.get("description_fn", lambda _: spec["description"])(obj)
        entry = {
            "name": name,
            "label": spec["label"],
            "description": description,
            "ui_variant": spec["ui_variant"],
            "enabled": enabled,
            "disabled_reason": disabled_reason,
        }
        group = spec["ui_group"]
        if group == "primary":
            primary = entry
        elif group == "secondary":
            secondary.append(entry)
        else:
            advanced.append(entry)
    return {"primary": primary, "secondary": secondary, "advanced": advanced}


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


class JournalOwnedTransitionView(JournalOwnedObjectMixin, JournalMemberRequiredMixin, View):

    TRANSITION_SPECS: dict = {}

    def check_transition_allowed(self, obj):
        return None

    def create_audit_note(self, obj, user, message):
        pass

    def get_success_url(self, obj):
        raise NotImplementedError

    def post(self, request, **kwargs):
        obj = self.get_object_or_404()

        guard = self.check_transition_allowed(obj)
        if guard:
            return guard

        transition_name = request.POST.get("transition", "")
        user_note = request.POST.get("note", "").strip()

        if transition_name not in self.TRANSITION_SPECS:
            return JsonResponse({"error": "Transition non autorisée."}, status=400)

        spec = self.TRANSITION_SPECS[transition_name]

        if precondition := spec.get("precondition"):
            ok, message = precondition(obj)
            if not ok:
                return JsonResponse({"error": message}, status=400)

        transition_method = getattr(obj, transition_name)
        if not can_proceed(transition_method):
            return JsonResponse({"error": "Transition impossible depuis l'état actuel."}, status=400)

        transition_method()
        obj.save()

        actor_name = request.user.get_full_name() or request.user.email
        msg = f"{actor_name} {spec['audit_verb']}"
        if user_note:
            msg += f" — {user_note}"
        self.create_audit_note(obj, request.user, msg)

        return JsonResponse({"ok": True, "redirect_url": self.get_success_url(obj)})
