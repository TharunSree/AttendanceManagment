# In accounts/decorators.py

from django.core.exceptions import PermissionDenied
from academics.navigation import REGISTERED_NAV_ITEMS

def admin_required(function):
    def wrap(request, *args, **kwargs):
        # Check if user is authenticated, has a profile, and the role is 'admin'
        if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'admin':
            return function(request, *args, **kwargs)
        else:
            # If not, raise a permission denied error
            raise PermissionDenied
    wrap.__doc__ = function.__doc__
    wrap.__name__ = function.__name__
    return wrap

# ... (admin_required decorator remains the same) ...

def nav_item(title, icon, url_name, roles=['admin'], group=None):
    """
    A decorator that registers a view as a sidebar navigation item.
    """
    def decorator(view_func):
        # Append a dictionary with all nav info to the central list
        REGISTERED_NAV_ITEMS.append({
            'title': title,
            'icon': icon,
            'url_name': url_name, # The full url name like 'academics:course_list'
            'roles': roles,
            'group': group
        })
        return view_func  # Return the original, unmodified view
    return decorator


# You can create other decorators like this later
# def faculty_required(function):
#     ...