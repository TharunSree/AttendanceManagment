# In academics/email_utils.py

from django.core.mail import get_connection, EmailMultiAlternatives
from .models import AttendanceSettings
import logging

logger = logging.getLogger(__name__)


# Add 'bcc_list=None' to the function signature
def send_database_email(subject, body, recipient_list, html_message=None, bcc_list=None):
    """
    Send email using SMTP settings from the database.
    Can handle a main recipient list and a BCC list for bulk sending.
    """
    settings = AttendanceSettings.load()

    if not settings.email_host:
        logger.error("SMTP settings are not configured. Cannot send email.")
        return False

    try:
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=settings.email_host,
            port=settings.email_port,
            username=settings.email_host_user,
            password=settings.email_host_password,
            use_tls=settings.email_use_tls,
            use_ssl=settings.email_use_ssl,
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=f"Attendance System <{settings.email_host_user}>",
            to=recipient_list,
            bcc=bcc_list,  # <-- Use the bcc_list here
            connection=connection
        )

        if html_message:
            email.attach_alternative(html_message, "text/html")

        email.send()
        logger.info(f"Email sent successfully to {recipient_list} and {len(bcc_list or [])} BCC recipients.")
        return True

    except Exception as e:
        logger.error(f"Failed to send email. Error: {e}")
        return False
