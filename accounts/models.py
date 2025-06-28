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

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    student_id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)

    # --- ADD THIS FOREIGN KEY to link a student to ONE class ---
    student_group = models.ForeignKey(
        'academics.StudentGroup',
        on_delete=models.SET_NULL,  # If class is deleted, student is not deleted
        null=True,
        blank=True,
        related_name='students'  # We can now get students via student_group.students.all()
    )

    # ... (field_of_expertise for faculty remains the same) ...
    field_of_expertise = models.ManyToManyField(
        Subject,
        blank=True,  # A teacher can be created without immediately assigning subjects
        help_text="For Faculty/HOD roles. Select the subjects this teacher specializes in."
    )

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


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