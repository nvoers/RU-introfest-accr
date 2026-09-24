import re

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def _rgb(color):
    match = HEX_RE.match(color or "")
    if not match:
        return None
    value = match.group(1)
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


@register.filter
def text_on(color):
    """Black or white text, whichever reads better on the given hex color."""
    rgb = _rgb(color)
    if rgb is None:
        return "inherit"
    r, g, b = (c / 255 for c in rgb)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#111827" if luminance > 0.55 else "#ffffff"


@register.simple_tag
def level_badge(level, size=""):
    """Colored pill for an access level (or a muted dash when unset)."""
    if level is None:
        return mark_safe('<span class="muted">—</span>')
    color = level.color if _rgb(level.color) else "#6b7280"
    return format_html(
        '<span class="badge badge-level {}" style="--level:{};color:{}">{}</span>',
        size,
        color,
        text_on(color),
        level.name,
    )


STATUS_CLASSES = {
    "Arrived": "badge-success",
    "Not Arrived": "badge-neutral",
    "Cancelled": "badge-danger",
}


@register.simple_tag
def status_badge(entry):
    return format_html(
        '<span class="badge {}">{}</span>',
        STATUS_CLASSES.get(entry.status, "badge-neutral"),
        entry.get_status_display(),
    )


@register.simple_tag
def icon(name, extra=""):
    return format_html(
        '<svg class="icon {}" aria-hidden="true"><use href="#i-{}"></use></svg>',
        extra,
        name,
    )


@register.filter
def percent(part, whole):
    try:
        return round((part or 0) / whole * 100) if whole else 0
    except (TypeError, ZeroDivisionError):
        return 0
