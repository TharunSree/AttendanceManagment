# academics/management/commands/check_low_attendance.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.db.models import Q
from django.utils import timezone # Import timezone
from datetime import timedelta # Import timedelta
import logging

from academics.models import AttendanceSettings, CourseSubject, AttendanceRecord, LowAttendanceNotification
from academics.email_utils import send_database_email

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Checks for students with low attendance and sends notifications if necessary, but no more than once a month.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting low attendance check...")

        try:
            settings = AttendanceSettings.load()
            required_percentage = settings.required_percentage

            active_students = User.objects.filter(profile__role='student', profile__student_group__isnull=False)

            for student in active_students:
                subjects = CourseSubject.objects.filter(course=student.profile.student_group.course)

                for subject in subjects:
                    # --- Robust Attendance Calculation (Unchanged) ---
                    total_classes = AttendanceRecord.objects.filter(
                        Q(student=student) &
                        (Q(timetable__subject=subject) | Q(extra_class__subject=subject))
                    ).count()
                    present_classes = AttendanceRecord.objects.filter(
                        Q(student=student) &
                        (Q(timetable__subject=subject) | Q(extra_class__subject=subject)) &
                        Q(status='Present')
                    ).count()
                    
                    if total_classes == 0:
                        continue
                    percentage = (present_classes / total_classes) * 100

                    if percentage < required_percentage:
                        # === THIS IS THE NEW "ONCE A MONTH" LOGIC ===
                        # Check for the most recent notification sent for this student/subject
                        last_notification = LowAttendanceNotification.objects.filter(
                            student=student, subject=subject
                        ).order_by('-sent_at').first()

                        # Set the notification cooldown period (e.g., 30 days)
                        cooldown_period = timedelta(days=30)

                        # We send a notification only if one has never been sent OR
                        # if the last one was sent more than 30 days ago.
                        if not last_notification or (timezone.now() - last_notification.sent_at > cooldown_period):
                            self.stdout.write(
                                f"Found low attendance for {student.username} in {subject.subject.name} ({percentage:.2f}%) - Sending notification."
                            )
                            if student.email:
                                # Email sending logic is the same
                                email_subject = f"Low Attendance Warning: {subject.subject.name}"
                                context = {
                                    'student': student, 'subject': subject,
                                    'current_percentage': percentage, 'required_percentage': required_percentage,
                                }
                                html_content = render_to_string('emails/low_attendance_warning.html', context)
                                text_content = f"Warning: Your attendance in {subject.subject.name} is {percentage:.2f}%, which is below the required minimum of {required_percentage}%."
                                
                                send_database_email(
                                    email_subject, text_content, [student.email], html_message=html_content
                                )
                                
                                # Log that a new notification was sent
                                LowAttendanceNotification.objects.create(
                                    student=student, subject=subject, attendance_percentage=percentage
                                )
                                self.stdout.write(f"  -> Notification sent to {student.email}")
                        else:
                            # If a notification was sent recently, we log it and do nothing
                            self.stdout.write(
                                f"Skipping {student.username} for {subject.subject.name} - notification sent recently."
                            )
                        # ===============================================
            
        except Exception as e:
            logger.error(f"An error occurred during the low attendance check: {e}")
            self.stderr.write(self.style.ERROR(f"An error occurred: {e}"))

        self.stdout.write(self.style.SUCCESS("Low attendance check complete."))
