import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from academics.models import AttendanceSettings


class Command(BaseCommand):
    help = 'Creates a database backup and rotates old backups.'

    def handle(self, *args, **kwargs):
        # Define the backup directory inside the project's root folder
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        self.stdout.write(f"Backup directory is {backup_dir}")

        # Load settings
        app_settings = AttendanceSettings.load()
        retention_days = app_settings.number_of_backups_to_retain

        # --- Create a new backup ---
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f'db_backup_{timestamp}.json'
        backup_filepath = os.path.join(backup_dir, backup_filename)

        self.stdout.write(f"Creating new backup: {backup_filepath}")
        try:
            # Use subprocess for better command execution
            with open(backup_filepath, 'w') as f:
                subprocess.run(
                    ['python', 'manage.py', 'dumpdata', '--indent=2'],
                    stdout=f,
                    check=True,
                    text=True
                )
            self.stdout.write(self.style.SUCCESS('Successfully created new backup.'))
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.stderr.write(self.style.ERROR(f"Backup failed: {e}"))
            return

        # --- Rotate old backups ---
        self.stdout.write("Checking for old backups to rotate...")
        try:
            all_backups = [f for f in os.listdir(backup_dir) if f.endswith('.json')]
            all_backups.sort(key=lambda name: os.path.getmtime(os.path.join(backup_dir, name)))

            num_backups_to_delete = len(all_backups) - retention_days

            if num_backups_to_delete > 0:
                self.stdout.write(
                    f"Found {len(all_backups)} backups. Deleting oldest {num_backups_to_delete} to meet retention policy of {retention_days}.")
                backups_to_delete = all_backups[:num_backups_to_delete]
                for backup_name in backups_to_delete:
                    os.remove(os.path.join(backup_dir, backup_name))
                    self.stdout.write(f"Deleted old backup: {backup_name}")
            else:
                self.stdout.write(self.style.SUCCESS("No old backups needed to be deleted."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during backup rotation: {e}"))
