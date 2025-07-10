from django.contrib.auth import user_login_failed, user_logged_in
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from academics.models import DailySubstitution
from .models import Profile, Notification, UserActivityLog


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    A signal to automatically create or save a Profile whenever a User is created or saved.
    """
    if created:
        Profile.objects.create(user=instance)
    # Ensure the profile is saved whenever the user object is saved.
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Profile)
def add_user_to_group(sender, instance, **kwargs):
    """
    A signal to automatically manage group membership based on profile role.
    This signal NO LONGER saves the user object.
    """
    ROLE_GROUP_MAP = {
        'admin': 'Admin',
        'faculty': 'Faculty',
        'student': 'Student',
    }

    if instance.role not in ROLE_GROUP_MAP:
        return

    user = instance.user
    target_group_name = ROLE_GROUP_MAP[instance.role]
    target_group, created = Group.objects.get_or_create(name=target_group_name)

    # Remove user from any other role-based groups to ensure they are only in one.
    all_role_groups = Group.objects.filter(name__in=ROLE_GROUP_MAP.values())
    user.groups.remove(*all_role_groups)

    # Add the user to their correct group
    target_group.user_set.add(user)


@receiver(post_save, sender=DailySubstitution)
def create_substitution_notification(sender, instance, created, **kwargs):
    """
    Creates a notification when a faculty member is assigned as a substitute.
    """
    if created:
        faculty_member = instance.substituted_by
        class_details = instance.timetable.subject.subject.name
        class_time = instance.timetable.time_slot.start_time.strftime("%I:%M %p")

        message = f"You have been assigned as a substitute for '{class_details}' at {class_time}."

        Notification.objects.create(
            recipient=faculty_member,
            message=message,
            url=reverse('academics:faculty_schedule')  # Link to their daily schedule
        )


def get_client_info(request):
    """Helper function to get the real client IP and User Agent."""

    # --- THIS IS THE FIX ---
    # Look for the X-Forwarded-For header first. If it's not there,
    # fall back to the standard REMOTE_ADDR.
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    # ---------------------

    user_agent = request.META.get('HTTP_USER_AGENT')
    return ip, user_agent


@receiver(user_logged_in)
def log_user_login_success(sender, request, user, **kwargs):
    """Log successful login attempts."""
    ip, user_agent = get_client_info(request)
    UserActivityLog.objects.create(
        user=user,
        username=user.username,
        action='login_success',
        ip_address=ip,
        user_agent=user_agent
    )


@receiver(user_login_failed)
def log_user_login_failure(sender, credentials, request, **kwargs):
    """Log failed login attempts."""
    ip, user_agent = get_client_info(request)
    UserActivityLog.objects.create(
        username=credentials.get('username', 'N/A'),
        action='login_failed',
        ip_address=ip,
        user_agent=user_agent
    )


@receiver(post_save, sender=User)
def set_superuser_profile_role(sender, instance, created, **kwargs):
    """
    Automatically sets the profile role to 'admin' for a newly created superuser.
    """
    if created and instance.is_superuser:
        try:
            # Get the profile associated with the new superuser
            profile = instance.profile
            # Set the role and save the profile
            profile.role = 'admin'
            profile.save()
        except Profile.DoesNotExist:
            # This case might happen in rare circumstances or during fixtures
            print(f"Warning: Profile for superuser {instance.username} not found. Could not set role.")
        except Exception as e:
            print(f"Error setting role for superuser {instance.username}: {e}")
