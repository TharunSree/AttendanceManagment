# In accounts/decorators.py

from django.core.exceptions import PermissionDenied

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

# You can create other decorators like this later
# def faculty_required(function):
#     ...