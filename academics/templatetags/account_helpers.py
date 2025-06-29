from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Custom template filter to allow dictionary key lookup with a variable.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
