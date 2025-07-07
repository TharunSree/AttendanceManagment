from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from academics.models import StudentGroup, Department, Subject  # Import the new models


class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('faculty', 'Faculty'),
        ('student', 'Student'),
        ('hod', 'Head of Department'),
    )
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    student_id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    parent_email = models.EmailField(max_length=255, blank=True, null=True)

    student_group = models.ForeignKey(
        'academics.StudentGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )

    field_of_expertise = models.ManyToManyField(
        Subject,
        blank=True,
        help_text="For Faculty/HOD roles. Select the subjects this teacher specializes in."
    )

    # --- NEW FIELDS TO ADD ---
    photo = models.ImageField(upload_to='student_photos/', null=True, blank=True, default='student_photos/default.png')
    father_name = models.CharField(max_length=100, blank=True)
    father_phone = models.CharField(max_length=15, blank=True)
    mother_name = models.CharField(max_length=100, blank=True)
    mother_phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)

    # -------------------------
    class Meta:
        permissions = [
            ("view_own_profile", "Can view own profile"),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old_instance = Profile.objects.get(pk=self.pk)
                if old_instance.photo and self.photo and old_instance.photo != self.photo:
                    # Check that we are not deleting the default photo
                    if 'default.png' not in old_instance.photo.path:
                        old_instance.photo.delete(save=False)
            except Profile.DoesNotExist:
                pass  # New object, nothing to delete.
        super().save(*args, **kwargs)


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    url = models.URLField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message[:30]}"

    class Meta:
        ordering = ['-timestamp']


class UserActivityLog(models.Model):
    ACTION_CHOICES = [
        ('login_success', 'Login Success'),
        ('login_failed', 'Login Failed'),
        ('logout', 'Logout'),
        ('session_timeout', 'Session Timeout'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=150, help_text="The username used in the action.")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.username} - {self.get_action_display()} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
