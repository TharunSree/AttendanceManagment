# academics/management/commands/check_low_attendance.py

import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.template.loader import render_to_string

from academics.email_utils import send_database_email
from academics.models import AttendanceSettings, CourseSubject, AttendanceRecord, LowAttendanceNotification

# It's good practice to have a logger for background tasks
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Checks for students with low attendance and sends notifications if necessary.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting low attendance check...")

        try:
            settings = AttendanceSettings.load()
            required_percentage = settings.required_percentage

            # Get all active students who are assigned to a class group
            active_students = User.objects.filter(profile__role='student', profile__student_group__isnull=False)

            for student in active_students:
                # Get all subjects relevant to the student's course
                subjects = CourseSubject.objects.filter(course=student.profile.student_group.course)

                for subject in subjects:
                    # --- Robust Attendance Calculation ---
                    # This query now counts attendance records linked to either a
                    # regular timetable class OR an extra class for this specific subject.

                    # Total classes held for this subject that the student was a part of
                    total_classes = AttendanceRecord.objects.filter(
                        Q(student=student) &
                        (Q(timetable__subject=subject) | Q(extra_class__subject=subject))
                    ).count()

                    # Classes the student was marked 'Present' for
                    present_classes = AttendanceRecord.objects.filter(
                        Q(student=student) &
                        (Q(timetable__subject=subject) | Q(extra_class__subject=subject)) &
                        Q(status='Present')
                    ).count()

                    # --- End of Calculation ---

                    # Skip if no attendance has been taken at all for this subject
                    if total_classes == 0:
                        continue

                    percentage = (present_classes / total_classes) * 100

                    # Check if the student's attendance is below the threshold
                    if percentage < required_percentage:
                        # Check if a notification has already been sent for this subject to avoid spamming the user
                        notification_sent = LowAttendanceNotification.objects.filter(student=student,
                                                                                     subject=subject).exists()

                        if not notification_sent:
                            self.stdout.write(
                                f"Found low attendance for {student.username} in {subject.subject.name} ({percentage:.2f}%)"
                            )

                            # Send an email notification if the student has an email address
                            if student.email:
                                email_subject = f"Low Attendance Warning: {subject.subject.name}"
                                context = {
                                    'student': student,
                                    'subject': subject,
                                    'current_percentage': percentage,
                                    'required_percentage': required_percentage,
                                }
                                html_content = render_to_string('emails/low_attendance_warning.html', context)
                                text_content = f"Warning: Your attendance in {subject.subject.name} is {percentage:.2f}%, which is below the required minimum of {required_percentage}%."

                                send_database_email(
                                    email_subject,
                                    text_content,
                                    [student.email],
                                    html_message=html_content
                                )

                                # Log that the notification was sent to prevent re-sending
                                LowAttendanceNotification.objects.create(
                                    student=student,
                                    subject=subject,
                                    attendance_percentage=percentage
                                )
                                self.stdout.write(f"  -> Notification sent to {student.email}")
                            else:
                                self.stdout.write(f"  -> SKIPPED: No email address found for {student.username}.")

        except Exception as e:
            logger.error(f"An error occurred during the low attendance check: {e}")
            self.stderr.write(self.style.ERROR(f"An error occurred: {e}"))

        self.stdout.write(self.style.SUCCESS("Low attendance check complete."))
