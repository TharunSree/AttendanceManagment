# academics/management/commands/cancel_missed_classes.py

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from academics.email_utils import send_database_email
from academics.models import Timetable, AttendanceRecord, AttendanceSettings, ClassCancellation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Checks for scheduled classes where attendance was not taken and marks them as cancelled.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting the auto-cancellation check for missed classes...'))

        try:
            settings = AttendanceSettings.load()
            # === THIS IS THE FIX: Using the correct setting in DAYS ===
            deadline_days = settings.mark_deadline_days
            # =========================================================

            now = timezone.now()

            # We check a reasonable window of the past few days to be safe
            dates_to_check = [now.date() - timedelta(days=i) for i in range(1, 5)]

            cancelled_classes_info = []

            for check_date in dates_to_check:
                day_of_week_str = check_date.strftime('%A')

                scheduled_classes = Timetable.objects.filter(
                    status='scheduled',
                    day_of_week=day_of_week_str
                )

                for tt_entry in scheduled_classes:
                    # The deadline is now the date of the class plus the deadline in days
                    cancellation_deadline_date = check_date + timedelta(days=deadline_days)

                    # We cancel if today's date is past the deadline date
                    if now.date() > cancellation_deadline_date:
                        has_attendance = AttendanceRecord.objects.filter(
                            timetable=tt_entry,
                            date=check_date
                        ).exists()

                        if not has_attendance:
                            # Perform the cancellation
                            tt_entry.status = 'cancelled'
                            tt_entry.save()

                            ClassCancellation.objects.get_or_create(
                                timetable=tt_entry,
                                date=check_date,
                                defaults={'cancelled_by': None}
                            )

                            info = f"Date: {check_date.strftime('%Y-%m-%d')}, Subject: {tt_entry.subject.subject.name}, Group: {tt_entry.student_group.name}"
                            cancelled_classes_info.append(info)

            # --- The email sending logic remains the same ---
            if cancelled_classes_info:
                recipient = settings.notification_recipient_email
                if recipient:
                    subject = f"System Alert: {len(cancelled_classes_info)} Classes Automatically Cancelled"
                    email_context = {'cancelled_classes': cancelled_classes_info}
                    html_content = render_to_string('emails/class_cancellation_alert.html', email_context)
                    plain_text_content = ("The following classes were automatically cancelled:\n\n" + "\n".join(
                        cancelled_classes_info))

                    send_database_email(subject, plain_text_content, [recipient], html_message=html_content)
                    self.stdout.write(self.style.SUCCESS(f"Sent notification email to {recipient}."))

                self.stdout.write(
                    self.style.SUCCESS(f'Successfully cancelled {len(cancelled_classes_info)} missed classes.'))
            else:
                self.stdout.write(self.style.SUCCESS('No missed classes found to cancel.'))

        except Exception as e:
            logger.error(f"An error occurred in the cancel_missed_classes command: {e}")
            self.stderr.write(self.style.ERROR(f"An error occurred: {e}"))