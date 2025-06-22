# In accounts/decorators.py
from academics.registry import REGISTERED_NAV_ITEMS

def nav_item(title, icon, url_name, permission=None, group=None, order=99):
    """
    Decorator that registers a view to be included in the sidebar.
    Visibility is now controlled by a specific Django permission codename.

    Args:
        permission (str): The codename of the permission required to see this link,
                          e.g., 'app_label.view_modelname'.
                          If None, any authenticated user can see it.
                          Superusers see all links automatically.
    """
    def decorator(view_func):
        REGISTERED_NAV_ITEMS.append({
            'title': title,
            'icon': icon,
            'url_name': url_name,
            'permission': permission,
            'group': group,
            'order': order
        })
        return view_func
    return decorator