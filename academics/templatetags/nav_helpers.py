# In academics/templatetags/nav_helpers.py

from django import template
from academics.registry import REGISTERED_NAV_ITEMS, NAVIGATION_GROUPS

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sidebar_nav(context):
    user = context['request'].user
    if not user.is_authenticated:
        return []

    # Filter all registered items by checking user permissions
    allowed_items = []
    for item in REGISTERED_NAV_ITEMS:
        required_perm = item.get('permission')

        # If no permission is listed, or if the user has the required permission, show the item.
        if not required_perm or user.has_perm(required_perm):
            allowed_items.append(item)

    # --- The rest of the function for sorting and grouping remains the same ---
    allowed_items.sort(key=lambda x: x.get('order', 99))

    items_by_group = {}
    ungrouped_items = []
    for item in allowed_items:
        group_id = item.get('group')
        if group_id:
            if group_id not in items_by_group:
                items_by_group[group_id] = []
            items_by_group[group_id].append(item)
        else:
            ungrouped_items.append(item)

    final_nav = []
    final_nav.extend(ungrouped_items)

    for group_def in NAVIGATION_GROUPS:
        # We only show a group if it has visible items inside it for the current user
        if group_def['id'] in items_by_group:
            group_copy = group_def.copy()
            group_copy['submenu'] = items_by_group[group_def['id']]
            final_nav.append(group_copy)

    final_nav.sort(key=lambda x: x.get('order', 0))
    return final_nav

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Custom template filter to allow dictionary key lookup with a variable.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None