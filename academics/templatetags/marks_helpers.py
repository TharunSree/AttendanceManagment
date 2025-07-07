from django import template

register = template.Library()


@register.filter(name='get_percentage')
def get_percentage(value, max_value):
    """
    Calculates the percentage.
    Usage: {{ marks_obtained|get_percentage:max_marks }}
    """
    if max_value is None or max_value == 0:
        return 0
    try:
        return (value / max_value) * 100
    except (ValueError, TypeError):
        return 0
