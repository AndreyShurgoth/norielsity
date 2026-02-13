from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def last_seen_human(value):
    if not value:
        return ""

    now = timezone.now()
    delta = now - value
    seconds = int(delta.total_seconds())

    if seconds < 60:
        return "щойно"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} хв тому"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} год тому"

    if hours < 48:
        return "вчора"

    return value.strftime("%d.%m.%Y %H:%M")
