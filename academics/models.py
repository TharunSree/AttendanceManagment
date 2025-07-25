from django.conf import settings  # To link to the User model
from django.contrib.auth.models import Group, User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q

from academics.thread_local import get_current_session


class CurrentSessionManager(models.Manager):
    """
    A custom model manager that AUTOMATICALLY filters querysets
    to only include objects from the currently active academic session.
    """

    def get_queryset(self):
        # Start with all objects
        queryset = super().get_queryset()

        # Get the current session that was set by the middleware
        current_session = get_current_session()

        if current_session:
            # Show classes that are currently active during this academic session
            # A class is active if the current session year falls within the class duration
            return queryset.filter(
                start_year__lte=current_session.start_year,  # Class started before or in current session
                passout_year__gte=current_session.start_year  # Class hasn't graduated yet
            )

        # If no session is active, return the unfiltered queryset
        return queryset

    def unfiltered(self):
        """A method to bypass the automatic filtering when needed."""
        return super().get_queryset()


class AcademicSession(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., '2024-2025'")
    start_year = models.PositiveIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    end_year = models.PositiveIntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    is_current = models.BooleanField(default=False, help_text="Mark the currently active academic session.")

    @classmethod
    def get_current_session(cls):
        """Returns the currently active academic session."""
        try:
            return cls.objects.get(is_current=True)
        except cls.DoesNotExist:
            return None
        except cls.MultipleObjectsReturned:
            # If multiple sessions are marked as current, return the latest one
            return cls.objects.filter(is_current=True).order_by('-start_year').first()

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
        return self.subject.name


class StudentGroup(models.Model):
    """ Represents a 'class' or 'batch' of students. """
    name = models.CharField(max_length=100, help_text="e.g., 'BCA Section A'")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='student_groups')
    start_year = models.PositiveIntegerField()
    passout_year = models.PositiveIntegerField()
    objects = CurrentSessionManager()

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
    STATUS_CHOICES = [  # <-- ADD THIS
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
    ]
    student_group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name='timetable_entries')
    subject = models.ForeignKey(CourseSubject, on_delete=models.CASCADE, related_name='timetable_entries')
    faculty = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timetable_entries',
                                limit_choices_to={'profile__role': 'faculty'})
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='timetable_entries')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

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
    passing_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=40.00,
        help_text="The minimum percentage required to pass a subject."
    )
    cancellation_threshold_hours = models.PositiveIntegerField(
        default=2,
        help_text="Hours after a class is scheduled that it will be auto-cancelled if attendance is not taken."
    )
    number_of_backups_to_retain = models.PositiveIntegerField(
        default=7,
        help_text="The number of recent daily backups to keep. Older backups will be deleted."
    )
    session_timeout_seconds = models.PositiveIntegerField(
        default=3600,  # Default to 1 hour
        help_text="The number of seconds of inactivity before a user is automatically logged out."
    )

    email_host = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., 'smtp.gmail.com'")
    email_port = models.PositiveIntegerField(default=587, help_text="e.g., 587 for TLS")
    email_host_user = models.EmailField(max_length=255, blank=True, null=True,
                                        help_text="The email address to send from.")
    email_host_password = models.CharField(max_length=255, blank=True, null=True,
                                           help_text="The email password or app password.")
    email_use_tls = models.BooleanField(default=True, help_text="Use TLS (Transport Layer Security). Recommended.")
    email_use_ssl = models.BooleanField(default=False,
                                        help_text="Use SSL (Secure Sockets Layer). Less common than TLS.")
    notification_recipient_email = models.EmailField(
        max_length=255, blank=True, null=True,
        help_text="The email address that receives system notifications (e.g., auto-cancellations)."
    )

    class Meta:
        verbose_name_plural = "Attendance Settings"

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
    # --- CHANGE 1: Make timetable nullable ---
    timetable = models.ForeignKey(
        'Timetable',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True,  # Allow null
        blank=True  # Allow blank in forms
    )
    # --- NEW: Add ForeignKey to ExtraClass ---
    extra_class = models.ForeignKey(
        'ExtraClass',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True,  # Allow null
        blank=True  # Allow blank in forms
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
        permissions = [
            ("view_own_attendance", "Can view own attendance page"),
        ]
        # --- CHANGE 2: Add constraints for data integrity ---
        constraints = [
            # Ensure that for each record, either timetable or extra_class is set, but not both.
            models.CheckConstraint(
                check=(
                        (Q(timetable__isnull=False) & Q(extra_class__isnull=True)) |
                        (Q(timetable__isnull=True) & Q(extra_class__isnull=False))
                ),
                name='one_of_timetable_or_extraclass'
            ),
            # New uniqueness constraints to replace the old unique_together
            models.UniqueConstraint(fields=['student', 'timetable', 'date'], name='unique_student_timetable_date',
                                    condition=Q(timetable__isnull=False)),
            models.UniqueConstraint(fields=['student', 'extra_class', 'date'], name='unique_student_extraclass_date',
                                    condition=Q(extra_class__isnull=False)),
        ]

    def __str__(self):
        session_type = "Timetable" if self.timetable else "Extra Class"
        return f"{self.student.username} on {self.date} ({session_type}) - {self.status}"


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


class ExtraClass(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('cancelled', 'Cancelled'),
    ]
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='extra_classes_taught')
    class_group = models.ForeignKey('StudentGroup', on_delete=models.CASCADE, related_name='extra_classes')
    # Use CourseSubject for consistency with Timetable
    subject = models.ForeignKey('CourseSubject', on_delete=models.CASCADE)
    date = models.DateField()
    # Use TimeSlot instead of start/end times
    time_slot = models.ForeignKey('TimeSlot', on_delete=models.CASCADE)
    announcement = models.ForeignKey('Announcement', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    class Meta:
        verbose_name_plural = "Extra Classes"
        # Prevent double booking a teacher or class for an extra class at the same time
        unique_together = (('teacher', 'date', 'time_slot'), ('class_group', 'date', 'time_slot'))

    def __str__(self):
        return f'Extra Class: {self.subject.subject.name} on {self.date} for {self.class_group}'


class ResultPublication(models.Model):
    """
    A log to track when a student's results for a specific semester
    have been officially published and sent to parents.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='published_results')
    student_group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE)
    semester = models.PositiveIntegerField()
    published_date = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='published_by_user')

    class Meta:
        # Ensure a student's results for a specific group/semester can only be published once
        unique_together = ('student', 'student_group', 'semester')

    def __str__(self):
        return f"Results for {self.student.username} (Sem {self.semester}) published on {self.published_date.strftime('%Y-%m-%d')}"


class LowAttendanceNotification(models.Model):
    """A log to track when a low attendance warning has been sent."""
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.ForeignKey(CourseSubject, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    attendance_percentage = models.FloatField()

    class Meta:
        unique_together = ('student', 'subject')  # Ensures only one log entry per student/subject

    def __str__(self):
        return f"Low attendance warning for {self.student.username} in {self.subject.subject.name}"


class StudentSubjectStatus(models.Model):
    """
    Tracks the official academic status of a student for a specific subject in a semester.
    This acts as the final 'locked' record after all marks are entered.
    """
    STATUS_CHOICES = [
        ('PASSED', 'Passed'),
        ('FAILED', 'Failed - Eligible for Supplementary'),
        ('PASSED_SUPPLEMENTARY', 'Passed in Supplementary'),
        ('FAILED_SUPPLEMENTARY', 'Failed in Supplementary'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subject_statuses')
    subject = models.ForeignKey(CourseSubject, on_delete=models.CASCADE, related_name='student_statuses')
    semester = models.PositiveIntegerField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)

    # This field will be updated when the status is finalized or changed.
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        # A student can only have one final status for a given subject in a semester.
        unique_together = ('student', 'subject', 'semester')
        ordering = ['student', 'semester', 'subject']

    def __str__(self):
        return f"{self.student.username} - {self.subject.subject.name} (Sem {self.semester}): {self.get_status_display()}"
