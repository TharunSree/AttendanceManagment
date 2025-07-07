# accounts/context_processors.py

from django.core.cache import cache
from .models import Notification, Profile


def custom_context_processor(request):
    # Start with an empty context dictionary
    context = {
        'unread_notification_count': 0,
        'recent_notifications': [],
        'update_count': 0,
    }

    if request.user.is_authenticated:
        # --- Your existing notification logic ---
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        recent_notifications = Notification.objects.filter(recipient=request.user, is_read=False)[:5]
        context['unread_notification_count'] = unread_count
        context['recent_notifications'] = recent_notifications

        # --- New logic for the update count ---
        # Get the update count from the cache, defaulting to 0 if not found
        context['update_count'] = cache.get('git_update_count', 0)
        try:
            profile = request.user.profile
            context['is_admin'] = profile.role == 'admin'
            context['is_faculty'] = profile.role == 'faculty'
            context['is_student'] = profile.role == 'student'
        except Profile.DoesNotExist:
            # Defaults are already False
            pass

    return context
