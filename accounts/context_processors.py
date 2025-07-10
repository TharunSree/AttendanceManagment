# In accounts/context_processors.py

import subprocess
import logging
from .models import Notification, Profile

logger = logging.getLogger(__name__)

def custom_context_processor(request):
    context = {
        'unread_notification_count': 0,
        'recent_notifications': [],
        'update_count': 0,
        'is_admin': False,
        'is_faculty': False,
        'is_student': False,
    }

    if request.user.is_authenticated:
        # --- Notification and User Role logic (unchanged) ---
        context['unread_notification_count'] = Notification.objects.filter(recipient=request.user, is_read=False).count()
        context['recent_notifications'] = Notification.objects.filter(recipient=request.user, is_read=False)[:5]
        try:
            profile = request.user.profile
            context['is_admin'] = profile.role == 'admin'
            context['is_faculty'] = profile.role == 'faculty'
            context['is_student'] = profile.role == 'student'
        except Profile.DoesNotExist:
            pass

        # --- DIRECT GIT CHECK LOGIC ---
        # If the user is an admin, we check the git status directly on page load.
        if context['is_admin']:
            try:
                # Define the project directory path
                project_dir = '/var/www/AttendanceManagment'

                # 1. Fetch the latest changes from the remote repo
                subprocess.run(['git', 'fetch'], check=True, cwd=project_dir)

                # 2. Compare local HEAD with the remote branch to count new commits
                result = subprocess.run(
                    ['git', 'rev-list', '--count', 'HEAD..origin/website-server'],
                    capture_output=True, text=True, check=True, cwd=project_dir
                )
                context['update_count'] = int(result.stdout.strip())
            except Exception as e:
                # If any git command fails, log the error and default to 0
                logger.error(f"Direct git update check failed: {e}")
                context['update_count'] = 0
        # --- END OF DIRECT GIT CHECK ---

    return context
