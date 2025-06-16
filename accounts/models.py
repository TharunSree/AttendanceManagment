from django.db import models
from django.contrib.auth.models import User
from academics.models import StudentGroup, Department  # Import the new models


class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('faculty', 'Faculty'),
        ('student', 'Student'),
        ('hod', 'Head of Department'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    # --- ADD THESE FIELDS ---
    student_id_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)

    # -------------------------

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"