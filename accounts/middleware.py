import time

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from academics.models import AttendanceSettings, AcademicSession
from academics.thread_local import set_current_session
from accounts.models import UserActivityLog


class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get timeout setting from database
            attendance_settings = AttendanceSettings.load()
            timeout_seconds = attendance_settings.session_timeout_seconds

            now = timezone.now().timestamp()
            last_activity = request.session.get('last_activity')

            # URLs that should NOT reset the session timeout
            # These are typically AJAX calls or background requests
            excluded_urls = [
                reverse('academics:check_announcements'),
                reverse('accounts:mark_notifications_as_read'),
                # Add other AJAX endpoints here as needed
            ]

            if last_activity:
                # Check if session has expired
                if now - last_activity > timeout_seconds:
                    UserActivityLog.objects.create(
                        user=request.user,
                        username=request.user.username,
                        action='session_timeout',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT')
                    )
                    logout(request)
                    return redirect('accounts:login')

            # Only update last_activity for non-excluded URLs
            if request.path not in excluded_urls:
                request.session['last_activity'] = now

        response = self.get_response(request)
        return response


class PerformanceBenchmarkMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        # Print the duration to the server console
        print(f"'{request.path}' took {duration:.4f} seconds to process.")
        return response


class AcademicSessionMiddleware(MiddlewareMixin):
    """
    This middleware finds the active academic session and makes it
    available globally for the duration of a single request.
    """

    def process_request(self, request):
        current_session = None
        try:
            current_session = AcademicSession.objects.get(is_current=True)
        except AcademicSession.DoesNotExist:
            # If no session is active, we do nothing.
            pass

        # Store the found session in a thread-safe local storage
        set_current_session(current_session)
