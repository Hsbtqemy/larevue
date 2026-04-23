import datetime

from django import template
from django.utils.html import mark_safe
from django.utils import timezone

from apps.core.display import VERDICT_LABELS, VERDICT_TONES
from apps.core.icons import ICONS

register = template.Library()

_SVG_ATTRS = (
    'fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round"'
)

_MONTH_SHORT = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]


# ------------------------------------------------------------------ #
# Inclusion tags                                                       #
# ------------------------------------------------------------------ #

@register.inclusion_tag("partials/_badge.html")
def state_badge(obj):
    return {
        "label": obj.get_state_display(),
        "tone": obj.get_badge_tone(),
    }


@register.inclusion_tag("partials/_badge.html")
def verdict_badge(verdict):
    return {
        "label": VERDICT_LABELS.get(verdict, verdict),
        "tone": VERDICT_TONES.get(verdict, "neutral"),
    }


@register.inclusion_tag("partials/_inline_editable.html")
def inline_editable(field, instance, url, input_type=None, options=None):
    value = getattr(instance, field, "")
    if value is None:
        value = ""

    resolved_type = input_type
    resolved_options = options or []

    if resolved_type is None:
        try:
            f = instance._meta.get_field(field)
        except Exception:
            f = None

        if f is not None:
            if f.choices:
                resolved_type = "select"
                resolved_options = list(f.choices)
            elif f.get_internal_type() == "DateField":
                resolved_type = "date"
            elif f.get_internal_type() == "TextField":
                resolved_type = "textarea"

    if resolved_type is None:
        resolved_type = "text"

    # Format date value for HTML date input
    display_value = value
    if isinstance(value, datetime.date):
        display_value = value.isoformat()

    return {
        "field_name": field,
        "value": display_value,
        "url": url,
        "type": resolved_type,
        "options": resolved_options,
    }


# ------------------------------------------------------------------ #
# Simple tags                                                          #
# ------------------------------------------------------------------ #

@register.simple_tag
def icon(name, size=16, cls=""):
    paths = ICONS.get(name, "")
    if not paths:
        return ""
    class_attr = f' class="{cls}"' if cls else ""
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" {_SVG_ATTRS}{class_attr}>'
        f"{paths}"
        f"</svg>"
    )
    return mark_safe(svg)


# ------------------------------------------------------------------ #
# Filters                                                              #
# ------------------------------------------------------------------ #

@register.filter
def date_short(value):
    """14 janv. 2026"""
    if not value:
        return ""
    return f"{value.day} {_MONTH_SHORT[value.month - 1]} {value.year}"


@register.filter
def date_compact(value):
    """14/01/26"""
    if not value:
        return ""
    return value.strftime("%d/%m/%y")


@register.filter
def date_calendar(value):
    """{'day': 14, 'month': 'janv'} — for dashboard calendar pills."""
    if not value:
        return {}
    return {
        "day": value.day,
        "month": _MONTH_SHORT[value.month - 1].rstrip("."),
    }


@register.filter
def days_late(value):
    """Days elapsed since value (positive = past, negative = future)."""
    if not value:
        return 0
    today = timezone.now().date()
    return (today - value).days
