import datetime
import json

from django import template
from django.utils.html import mark_safe
from django.utils import timezone

from apps.core.display import MONTH_ABBR, MONTH_SHORT, VERDICT_LABELS, VERDICT_TONES
from apps.core.icons import ICONS

register = template.Library()

_SVG_ATTRS = (
    'fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"'
)


def _infer_input_type(field_obj):
    if field_obj.choices:
        return "select"
    ft = field_obj.get_internal_type()
    if ft == "DateField":
        return "date"
    if ft == "TextField":
        return "textarea"
    return "text"


@register.inclusion_tag("partials/_badge.html")
def state_badge(obj):
    return {"label": obj.get_state_display(), "tone": obj.get_badge_tone()}


@register.inclusion_tag("partials/_badge.html")
def verdict_badge(verdict):
    return {
        "label": VERDICT_LABELS.get(verdict, verdict),
        "tone": VERDICT_TONES.get(verdict, "neutral"),
    }


@register.inclusion_tag("partials/_inline_editable.html")
def inline_editable(field, instance, url, input_type=None, options=None, datalist_id=None, datalist_options=None, placeholder=None):
    value = getattr(instance, field, "") or ""
    resolved_options = list(options) if options else []

    if input_type is None:
        try:
            f = instance._meta.get_field(field)
            input_type = _infer_input_type(f)
            if input_type == "select" and not resolved_options:
                resolved_options = list(f.choices)
        except Exception:
            input_type = "text"

    if isinstance(value, datetime.date):
        value = value.isoformat()

    return {
        "field_name": field,
        "value": value,
        "url": url,
        "type": input_type,
        "options": resolved_options,
        "datalist_id": datalist_id,
        "datalist_options": datalist_options or [],
        "placeholder": placeholder or "—",
    }


@register.simple_tag
def icon(name, size=16, cls=""):
    paths = ICONS.get(name, "")
    if not paths:
        return ""
    class_attr = f' class="{cls}"' if cls else ""
    return mark_safe(
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" {_SVG_ATTRS}{class_attr}>'
        f"{paths}</svg>"
    )


@register.filter
def image_url(value):
    """Return the URL for a FileField/ImageField, or '' if the field is empty."""
    return value.url if value else ""


@register.filter
def date_short(value):
    if not value:
        return ""
    return f"{value.day} {MONTH_SHORT[value.month - 1]} {value.year}"


@register.filter
def date_compact(value):
    if not value:
        return ""
    return value.strftime("%d/%m/%y")


@register.filter
def date_calendar(value):
    if not value:
        return {}
    return {"day": value.day, "month": MONTH_ABBR[value.month - 1]}


@register.filter
def days_late(value):
    if not value:
        return 0
    return (datetime.date.today() - value).days


@register.filter
def timesince_short(value):
    """Relative time in French: 'il y a 2 h', 'il y a 3 jours', etc."""
    if not value:
        return ""
    now = timezone.now()
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    seconds = max(0, int((now - value).total_seconds()))
    days = seconds // 86400
    if seconds < 60:
        return "à l'instant"
    if seconds < 3600:
        return f"il y a {seconds // 60} min"
    if seconds < 86400:
        return f"il y a {seconds // 3600} h"
    if days < 7:
        return f"il y a {days} jour{'s' if days > 1 else ''}"
    if days < 30:
        n = days // 7
        return f"il y a {n} semaine{'s' if n > 1 else ''}"
    if days < 365:
        n = days // 30
        return f"il y a {n} mois"
    return value.strftime("le %d/%m/%Y")


@register.filter
def to_json(value):
    """Serialize a Python value to a safe JSON string for use in Alpine.js data attributes."""
    return mark_safe(json.dumps(value))
