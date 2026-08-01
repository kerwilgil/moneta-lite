from django import template

register = template.Library()


@register.simple_tag
def accessible_widget(bound_field):
    """Render a form control connected to its help and error messages."""
    described_by = []
    if bound_field.help_text:
        described_by.append(f"{bound_field.auto_id}-help")
    if bound_field.errors:
        described_by.append(f"{bound_field.auto_id}-error")
    attrs = {}
    if described_by:
        attrs["aria-describedby"] = " ".join(described_by)
    if bound_field.errors:
        attrs["aria-invalid"] = "true"
    return bound_field.as_widget(attrs=attrs)


@register.filter
def service_icon(service_name):
    text = (service_name or "").lower()
    icon_map = {
        "spotify": "🎧",
        "youtube": "▶️",
        "netflix": "🎬",
        "hbo": "🎞️",
        "disney": "🏰",
        "instagram": "📸",
        "apple music": "🎵",
        "prime": "📦",
        "seguro": "🛡️",
        "vida": "💟",
    }
    for key, icon in icon_map.items():
        if key in text:
            return icon
    return "📌"
