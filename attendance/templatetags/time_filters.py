from django import template

register = template.Library()

@register.filter
def format_12hr(time_obj):
    """
    Format a time object to 12-hour format with AM/PM.
    Example: datetime.time(14, 30) -> "02:30 PM"
    """
    if not time_obj:
        return ''
    try:
        return time_obj.strftime('%I:%M %p')
    except Exception:
        return str(time_obj)
