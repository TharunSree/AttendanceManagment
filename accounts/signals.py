from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    This signal automatically creates a Profile whenever a new User is created.
    """
    if created:
        # The role will be set to 'student' by default.
        # An admin can change this later if they create a faculty member.
        Profile.objects.create(user=instance, role='student')

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    This signal automatically saves the profile whenever the User object is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()