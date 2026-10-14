import re

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

HEX_RE = re.compile(r"^#([0-9a-fA-F]{6})$")


def _rgb(color):
    match = HEX_RE.match(color or "")
    if not match:
        return None
    value = match.group(1)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


@register.filter
def text_on(color):
    """Readable text color (near-black or white) on a hex background."""
    rgb = _rgb(color)
    if rgb is None:
        return "#ffffff"
    r, g, b = (c / 255 for c in rgb)
    return "#111827" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.58 else "#ffffff"


@register.simple_tag
def icon(name, cls=""):
    return format_html(
        '<svg class="icon {}" aria-hidden="true"><use href="#i-{}"></use></svg>', cls, name
    )


@register.simple_tag
def pill(obj, cls=""):
    """Solid colored pill for anything with .name and .color (type, zone, stage, team)."""
    if obj is None:
        return mark_safe('<span class="muted">—</span>')
    color = obj.color if _rgb(obj.color) else "#64748b"
    return format_html(
        '<span class="pill {}" style="--c:{};color:{}">{}</span>',
        cls,
        color,
        text_on(color),
        getattr(obj, "code", "") or obj.name if cls == "code" else obj.name,
    )


@register.simple_tag
def dot(obj):
    color = obj.color if obj is not None and _rgb(obj.color) else "#94a3b8"
    return format_html('<span class="dot" style="--c:{}"></span>', color)


STATUS_TONE = {
    "draft": "neutral",
    "pending": "warning",
    "approved": "success",
    "rejected": "danger",
    "cancelled": "neutral",
    "not_started": "neutral",
    "in_progress": "info",
    "submitted": "warning",
    "complete": "success",
    "requested": "warning",
    "confirmed": "success",
    "declined": "danger",
}


@register.simple_tag
def status(obj, field="status"):
    value = getattr(obj, field)
    label = getattr(obj, f"get_{field}_display")()
    return format_html(
        '<span class="badge tone-{}">{}</span>', STATUS_TONE.get(value, "neutral"), label
    )


@register.filter
def percent(part, whole):
    try:
        return min(100, round((part or 0) / whole * 100)) if whole else 0
    except (TypeError, ZeroDivisionError):
        return 0


@register.filter
def get(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def active(context, *names):
    """aria-current for sidebar links whose url name starts with one of names."""
    match = context["request"].resolver_match
    current = match.url_name if match else ""
    if any(current == n or current.startswith(n + "_") for n in names):
        return mark_safe(' aria-current="page"')
    return ""


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """Current query string with some keys replaced (None/'' removes a key)."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
