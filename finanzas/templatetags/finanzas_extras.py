from django import template

register = template.Library()


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
