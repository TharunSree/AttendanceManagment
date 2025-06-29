from django.contrib.auth.models import Group
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings  # To link to the User model


class AcademicSession(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., '2024-2025'")
    start_year = models.PositiveIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    end_year = models.PositiveIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    is_current = models.BooleanField(default=False, help_text="Mark the currently active academic session.")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-start_year']


class Department(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Optional department code")
    # This is now a confirmed requirement
    head_of_department = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='led_departments',
        limit_choices_to={'profile__role': 'faculty'}  # Assumes User has a related 'profile' with a 'role'
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Subject(models.Model):
    SUBJECT_TYPE_CHOICES = [
        ('theory', 'Theory'),
        ('practical', 'Practical'),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPE_CHOICES, default='theory')
    description = models.TextField(blank=True)
    required_hours = models.IntegerField(default=40, help_text="Default required hours for this subject")

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['name']


class Course(models.Model):
    COURSE_TYPE_CHOICES = [
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
    ]
    name = models.CharField(max_length=200, unique=True)
    course_type = models.CharField(max_length=2, choices=COURSE_TYPE_CHOICES, default='UG')
    duration_years = models.PositiveIntegerField(default=3)
    required_hours_per_semester = models.PositiveIntegerField(default=300)

    # --- ADD THIS NEW FIELD ---
    description = models.TextField(blank=True, null=True)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='courses')
    marking_scheme = models.ForeignKey(
        'MarkingScheme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The grading scheme used for this course."
    )

    def __str__(self):
        return self.name


class CourseSubject(models.Model):
    """This 'through' model connects a Course to its Subjects and adds the required hours."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    required_hours = models.PositiveIntegerField(default=40,
                                                 help_text="Total hours required for this subject in this course.")
    semester = models.PositiveIntegerField(
        help_text="e.g., 1, 2, 3 for the semester number."
    )

    class Meta:
        unique_together = ('course', 'subject')  # A subject can only be in a course once

    def __str__(self):
        return f"{self.course.name} - {self.subject.name} ({self.required_hours} hrs)"


class StudentGroup(models.Model):
    """ Represents a 'class' or 'batch' of students. """
    name = models.CharField(max_length=100, help_text="e.g., 'BCA Section A'")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='student_groups')
    start_year = models.PositiveIntegerField()
    passout_year = models.PositiveIntegerField()

    def __str__(self):
        # Now it uses the dedicated name field
        return self.name

    class Meta:
        # A course can have multiple classes, but their names should be unique for a given course
        unique_together = ('name', 'course')
        ordering = ['name']


class TimeSlot(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()
    # --- NEW FIELD ---
    label = models.CharField(max_length=50, blank=True, null=True,
                             help_text="Optional label to display instead of time (e.g., 'LUNCH').")
    is_schedulable = models.BooleanField(default=True, help_text="Uncheck for breaks like Lunch.")

    def __str__(self):
        if self.label:
            return f"{self.label} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    class Meta:
        ordering = ['start_time']


class Timetable(models.Model):
    DAY_CHOICES = [
        ('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'), ('Friday', 'Friday'), ('Saturday', 'Saturday'), ('Sunday', 'Sunday')
    ]
    student_group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name='timetable_entries')
    subject = models.ForeignKey(CourseSubject, on_delete=models.CASCADE, related_name='timetable_entries')
    faculty = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timetable_entries',
                                limit_choices_to={'profile__role': 'faculty'})
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='timetable_entries')

    class Meta:
        permissions = [
            ("view_own_timetable", "Can view own timetable"),
        ]
        # Prevent double booking a teacher or a class group at the same time
        unique_together = (('day_of_week', 'time_slot', 'faculty'), ('day_of_week', 'time_slot', 'student_group'))

    def __str__(self):
        return f"{self.student_group} | {self.subject.subject.name} | {self.day_of_week} at {self.time_slot}"


class AttendanceSettings(models.Model):
    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)
    required_percentage = models.PositiveIntegerField(default=75,
                                                      validators=[MinValueValidator(0), MaxValueValidator(100)])

    # --- NEW FIELDS ---
    mark_deadline_days = models.PositiveIntegerField(default=1,
                                                     help_text="Number of days a faculty has to mark attendance.")
    edit_deadline_days = models.PositiveIntegerField(default=3,
                                                     help_text="Number of days a faculty has to edit attendance after marking.")

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Global Attendance Settings"


class AttendanceRecord(models.Model):
    """
    This model represents a single attendance entry for a student in a specific class on a specific day.
    """
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        limit_choices_to={'profile__role': 'student'}
    )
    timetable = models.ForeignKey(
        'Timetable',  # Use a string to avoid circular import issues
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    is_late = models.BooleanField(default=False)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendance',
        limit_choices_to={'profile__role__in': ['faculty', 'admin']}
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A student can only have one attendance status for a specific class on a specific date
        unique_together = ('student', 'timetable', 'date')
        permissions = [
            ("view_own_attendance", "Can view own attendance page"),
        ]

    def __str__(self):
        return f"{self.student.username} on {self.date} - {self.status}"


class ClassCancellation(models.Model):
    """
    A record to indicate that a scheduled class was not conducted on a specific day.
    """
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='cancellations')
    date = models.DateField()
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        # A class can only be cancelled once per day
        unique_together = ('timetable', 'date')

    def __str__(self):
        return f"Cancelled: {self.timetable} on {self.date}"


class DailySubstitution(models.Model):
    """
    Represents a temporary, one-day substitution for a scheduled timetable entry.
    """
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='substitutions')
    date = models.DateField()
    substituted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name='substitute_classes', limit_choices_to={'profile__role': 'faculty'})

    class Meta:
        # A specific class period on a specific day can only have one substitute.
        unique_together = ('timetable', 'date')

    def __str__(self):
        return f"{self.timetable} on {self.date} substituted by {self.substituted_by.get_full_name()}"


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # --- MODIFIED FIELDS ---
    target_student_groups = models.ManyToManyField(
        StudentGroup,
        blank=True,
        help_text="Select specific classes to send this to."
    )
    send_to_all_students = models.BooleanField(default=False)
    send_to_all_faculty = models.BooleanField(default=False)
    # -----------------------

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        permissions = [("can_send_announcement", "Can send announcements")]

    def __str__(self):
        return self.title


class UserNotificationStatus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    is_seen = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'announcement')


class MarkingScheme(models.Model):
    """
    A scheme designed by the admin, containing various criteria for evaluation.
    e.g., "Semester End Exam Scheme"
    """
    name = models.CharField(max_length=100, unique=True, help_text="e.g., 'Default Grading Scheme'")

    def __str__(self):
        return self.name


class Criterion(models.Model):
    """
    A specific criterion within a marking scheme, like 'Internal Exam' or 'Assignment'.
    """
    name = models.CharField(max_length=100)
    scheme = models.ForeignKey(MarkingScheme, on_delete=models.CASCADE, related_name='criteria')
    max_marks = models.PositiveIntegerField(default=100)

    class Meta:
        unique_together = ('scheme', 'name')

    def __str__(self):
        return f"{self.name} ({self.max_marks} marks)"


class Mark(models.Model):
    """
    Stores the marks obtained by a student for a specific criterion in a subject.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marks',
        limit_choices_to={'profile__role': 'student'}
    )
    subject = models.ForeignKey(CourseSubject, on_delete=models.CASCADE, related_name='marks')
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name='marks')
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2,
                                         validators=[MinValueValidator(0.0)])

    class Meta:
        unique_together = ('student', 'subject', 'criterion')
        ordering = ['subject', 'criterion']
        permissions = [
            ("view_own_marks", "Can view own marks"),
        ]

    def __str__(self):
        return f"Mark for {self.student.username} in {self.subject.subject.name} ({self.criterion.name})"
