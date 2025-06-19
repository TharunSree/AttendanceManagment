# academics/templatetags/nav_helpers.py (Final Reliable Version)

from django import template
from academics.navigation import REGISTERED_NAV_ITEMS, NAVIGATION_GROUPS

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sidebar_nav(context):
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return []

    user_role = getattr(request.user.profile, 'role', 'guest')

    # Filter the auto-registered items by the current user's role
    allowed_items = [item for item in REGISTERED_NAV_ITEMS if user_role in item['roles']]

    # Create a lookup dictionary to organize items by their group
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

    # Build the final navigation structure
    final_nav = []
    final_nav.extend(ungrouped_items)

    for group in NAVIGATION_GROUPS:
        if user_role in group['roles'] and group['id'] in items_by_group:
            group_copy = group.copy()
            group_copy['submenu'] = items_by_group[group['id']]
            final_nav.append(group_copy)

    return final_nav