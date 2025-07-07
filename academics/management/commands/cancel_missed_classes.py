import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from academics.models import Timetable, AttendanceRecord, AttendanceSettings, ClassCancellation

# Configure logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Checks for scheduled classes where attendance was not taken and marks them as cancelled.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting the auto-cancellation check for missed classes...'))

        try:
            # Load settings
            settings = AttendanceSettings.load()
            threshold_hours = settings.cancellation_threshold_hours
            now = datetime.now()
            cancellation_deadline = now - timedelta(hours=threshold_hours)

            # Find potentially missed classes
            # - Must be a scheduled class (not already cancelled)
            # - The scheduled time must have passed
            # - The time must be older than the cancellation deadline

            # Note: This logic assumes a simple mapping of day_of_week to date.
            # A more complex system might need to check against a holiday calendar.
            day_of_week_map = {
                'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
                'Friday': 4, 'Saturday': 5, 'Sunday': 6
            }
            today_str = now.strftime('%A')  # e.g., 'Monday'

            # We look for classes scheduled today, up to the cancellation deadline time
            potentially_missed_classes = Timetable.objects.filter(
                status='scheduled',
                day_of_week=today_str,
                time_slot__start_time__lt=cancellation_deadline.time()
            )

            if not potentially_missed_classes.exists():
                self.stdout.write(self.style.SUCCESS('No classes found within the cancellation window.'))
                return

            cancelled_count = 0
            cancelled_classes_info = []
            for tt_entry in potentially_missed_classes:
                # Check if any attendance record exists for this timetable entry on today's date
                has_attendance = AttendanceRecord.objects.filter(
                    Q(timetable=tt_entry) | Q(extra_class__timetable=tt_entry),
                    # Checks both regular and extra classes linked to this slot
                    date=now.date()
                ).exists()

                if not has_attendance:
                    # No attendance was taken, so cancel the class
                    tt_entry.status = 'cancelled'
                    tt_entry.save()
                    ClassCancellation.objects.get_or_create(
                        timetable=tt_entry,
                        date=now.date(),
                        defaults={'cancelled_by': None}
                    )
                    cancelled_count += 1
                    self.stdout.write(f"Cancelled: {tt_entry} on {now.date().strftime('%Y-%m-%d')}")
                    info = f"- Subject: {tt_entry.subject.subject.name}, Faculty: {tt_entry.faculty.get_full_name()}, Group: {tt_entry.student_group.name}, Time: {tt_entry.time_slot.start_time.strftime('%H:%M')}"
                    cancelled_classes_info.append(info)
            if cancelled_classes_info:
                recipient = settings.notification_recipient_email
                if recipient:
                    subject = f"System Alert: {len(cancelled_classes_info)} Classes Automatically Cancelled"
                    email_body = (
                        "This is an automated notification from the Attendance Management System.\n\n"
                        "The following scheduled classes were automatically cancelled because attendance was not marked within the configured time limit:\n\n"
                    )
                    email_body += "\n".join(cancelled_classes_info)
                    email_body += "\n\nNo action is required, this is for your information."

                    send_database_email(subject, email_body, [recipient])
                    self.stdout.write(self.style.SUCCESS(f"Sent notification email to {recipient}."))
                else:
                    self.stdout.write(self.style.WARNING(
                        "Classes were cancelled, but no notification recipient email is configured in settings."))

            if cancelled_count > 0:
                self.stdout.write(self.style.SUCCESS(f'Successfully cancelled {cancelled_count} missed classes.'))
            else:
                self.stdout.write(
                    self.style.SUCCESS('All due classes had attendance marked. No classes were cancelled.'))

        except Exception as e:
            logger.error(f"An error occurred in the cancel_missed_classes command: {e}")
            self.stderr.write(self.style.ERROR(f"An error occurred: {e}"))
