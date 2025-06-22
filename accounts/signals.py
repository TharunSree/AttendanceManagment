from django.db.models.signals import post_save
from django.contrib.auth.models import User, Group
from django.dispatch import receiver
from .models import Profile


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