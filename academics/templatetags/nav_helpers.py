from django import template
from collections import defaultdict
from django.urls import resolve
from academics.registry import (
    REGISTERED_NAV_ITEMS,
    NAVIGATION_GROUPS,
    SUBGROUP_DEFINITIONS,
    SUBGROUP_MAPPING
)

register = template.Library()


@register.simple_tag(takes_context=True)
def get_sidebar_nav(context):
    user = context['request'].user
    if not user.is_authenticated:
        return []

    # Get the name of the current URL to determine the active item/group
    current_url_name = resolve(context['request'].path_info).url_name

    # Filter items based on user permissions
    allowed_items = [
        item for item in REGISTERED_NAV_ITEMS
        if not item.get('permission') or user.has_perm(item['permission'])
    ]

    # This will hold the final structure for each main group
    items_by_group = defaultdict(lambda: {'direct_items': [], 'subgroups': defaultdict(list)})
    ungrouped_items = []

    for item in allowed_items:
        group_id = item.get('group')
        if group_id:
            subgroup_id = SUBGROUP_MAPPING.get(item['url_name'])
            if subgroup_id:
                items_by_group[group_id]['subgroups'][subgroup_id].append(item)
            else:
                items_by_group[group_id]['direct_items'].append(item)
        else:
            ungrouped_items.append(item)

    final_nav = []
    final_nav.extend(sorted(ungrouped_items, key=lambda x: x.get('order', 99)))

    for group_def in NAVIGATION_GROUPS:
        group_id = group_def['id']
        if group_id in items_by_group:
            group_content = items_by_group[group_id]

            # Process collapsible subgroups
            processed_subgroups = []
            for subgroup_id, items in group_content['subgroups'].items():
                subgroup_def = SUBGROUP_DEFINITIONS.get(subgroup_id, {})
                is_subgroup_active = any(item['url_name'] == current_url_name for item in items)
                processed_subgroups.append({
                    'id': f"subgroup-{group_id}-{subgroup_id}",
                    'title': subgroup_def.get('title', 'Subgroup'),
                    'order': subgroup_def.get('order', 99),
                    'items': sorted(items, key=lambda x: x.get('order', 99)),
                    'is_active': is_subgroup_active
                })
            processed_subgroups.sort(key=lambda x: x['order'])

            # Process direct items
            direct_items = sorted(group_content['direct_items'], key=lambda x: x.get('order', 99))

            # Determine if the main group should be active
            is_main_group_active = (
                any(item['url_name'] == current_url_name for item in direct_items) or
                any(sg['is_active'] for sg in processed_subgroups)
            )

            # Create the final structure for this main group
            group_copy = group_def.copy()
            group_copy['is_active'] = is_main_group_active
            group_copy['submenu_content'] = {
                'direct_items': direct_items,
                'subgroups': processed_subgroups
            }
            final_nav.append(group_copy)

    final_nav.sort(key=lambda x: x.get('order', 0))
    return final_nav