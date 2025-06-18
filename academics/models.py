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

    class Meta:
        unique_together = ('start_time', 'end_time')
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


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
        # Prevent double booking a teacher or a class group at the same time
        unique_together = (('day_of_week', 'time_slot', 'faculty'), ('day_of_week', 'time_slot', 'student_group'))

    def __str__(self):
        return f"{self.student_group} | {self.subject.subject.name} | {self.day_of_week} at {self.time_slot}"


class AttendanceSettings(models.Model):
    """
    A singleton model to store site-wide attendance settings.
    This ensures there is only ever one row of settings in the database.
    """
    # The 'pk' is explicitly set to 1 to ensure it's a singleton
    id = models.PositiveIntegerField(primary_key=True, default=1, editable=False)
    required_percentage = models.PositiveIntegerField(
        default=75,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum attendance percentage required for students to be eligible."
    )

    def __str__(self):
        return "Global Attendance Settings"

    def save(self, *args, **kwargs):
        # Enforce that this object always has a primary key of 1
        self.pk = 1
        super(AttendanceSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # A convenient class method to get the settings object,
        # creating it if it doesn't exist.
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name_plural = "Attendance Settings"


class AttendanceRecord(models.Model):
    """
    This model represents a single attendance entry for a student in a specific class on a specific day.
    """
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Excused', 'Excused'),
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
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendance',
        limit_choices_to={'profile__role__in': ['faculty', 'admin']}
    )

    class Meta:
        # A student can only have one attendance status for a specific class on a specific date
        unique_together = ('student', 'timetable', 'date')

    def __str__(self):
        return f"{self.student.username} on {self.date} - {self.status}"