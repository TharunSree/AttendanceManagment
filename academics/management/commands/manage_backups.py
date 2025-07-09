import json
import os
from datetime import datetime

from django.core import serializers
from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import *
from accounts.models import Profile


class Command(BaseCommand):
    help = 'Enhanced backup and restore system for academic data'

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['backup', 'restore', 'list'], help='Action to perform')
        parser.add_argument('--file', type=str, help='Backup file path')
        parser.add_argument('--verify', action='store_true', help='Verify data after restore')
        parser.add_argument('--clear', action='store_true', help='Clear existing data before restore')
        parser.add_argument('--preserve-superusers', action='store_true',
                            help='Preserve superuser accounts during restore')

    def handle(self, *args, **options):
        if options['action'] == 'backup':
            self.create_backup(options.get('file'))
        elif options['action'] == 'restore':
            self.restore_backup(options.get('file'), options.get('verify', False), options.get('clear', False))
        elif options['action'] == 'list':
            self.list_backups()

    def clear_database(self):
        """Clear all data from the database in reverse dependency order"""
        models_to_clear = [
            # Clear in reverse order to avoid foreign key constraints
            Mark,
            Criterion,
            MarkingScheme,
            UserNotificationStatus,
            Announcement,
            DailySubstitution,
            ClassCancellation,
            AttendanceRecord,
            AttendanceSettings,
            Timetable,
            CourseSubject,
            Profile,
            TimeSlot,
            StudentGroup,
            Course,
            Subject,
            AcademicSession,
            # Keep User for last but don't delete superusers
        ]

        for model in models_to_clear:
            count = model.objects.count()
            if count > 0:
                model.objects.all().delete()
                self.stdout.write(f'Cleared {count} {model._meta.label} objects')

        # Clear non-superuser accounts
        non_superuser_count = User.objects.filter(is_superuser=False).count()
        if non_superuser_count > 0:
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(f'Cleared {non_superuser_count} non-superuser User objects')

    def create_backup(self, file_path=None):
        """Create a comprehensive backup with proper data ordering"""
        if not file_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = f'backup_{timestamp}.json'

        # Define models in dependency order
        models_to_backup = [
            User,
            AcademicSession,
            Subject,
            Course,
            StudentGroup,
            TimeSlot,
            Profile,
            CourseSubject,
            Timetable,
            AttendanceSettings,
            AttendanceRecord,
            ClassCancellation,
            DailySubstitution,
            Announcement,
            UserNotificationStatus,
            MarkingScheme,
            Criterion,
            Mark,
        ]

        backup_data = []

        for model in models_to_backup:
            model_data = serializers.serialize('json', model.objects.all())
            if model_data != '[]':
                parsed_data = json.loads(model_data)
                backup_data.extend(parsed_data)

        with open(file_path, 'w') as f:
            json.dump(backup_data, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f'Backup created successfully: {file_path}')
        )
        self.print_backup_summary(backup_data)

    @transaction.atomic
    def restore_backup(self, file_path, verify=False, clear_existing=False):
        """Restore backup with proper error handling and verification"""
        if not file_path or not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f'Backup file not found: {file_path}')
            )
            return

        if clear_existing:
            self.stdout.write("Clearing existing data...")
            self.clear_database()

        with open(file_path, 'r') as f:
            backup_data = json.load(f)

        # Group data by model
        models_data = {}
        for item in backup_data:
            model_name = item['model']
            if model_name not in models_data:
                models_data[model_name] = []
            models_data[model_name].append(item)

        # Restore in specific order
        restore_order = [
            'auth.user',
            'academics.academicsession',
            'academics.subject',
            'academics.course',
            'academics.studentgroup',
            'academics.timeslot',
            'accounts.profile',
            'academics.coursesubject',
            'academics.timetable',
            'academics.attendancesettings',
            'academics.attendancerecord',
            'academics.classcancellation',
            'academics.dailysubstitution',
            'academics.announcement',
            'academics.usernotificationstatus',
            'academics.markingscheme',
            'academics.criterion',
            'academics.mark',
        ]

        restored_count = 0
        for model_name in restore_order:
            if model_name in models_data:
                try:
                    model_json = json.dumps(models_data[model_name])

                    for obj in serializers.deserialize('json', model_json):
                        # Skip superusers to avoid conflicts
                        if model_name == 'auth.user' and obj.object.is_superuser:
                            continue
                        obj.save()
                        restored_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Restored {len(models_data[model_name])} {model_name} objects'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error restoring {model_name}: {str(e)}')
                    )

        self.stdout.write(
            self.style.SUCCESS(f'Restore completed. Total objects restored: {restored_count}')
        )

        if verify:
            self.verify_restore()

    def verify_restore(self):
        """Verify that data was restored correctly"""
        self.stdout.write("\nVerifying restored data...")

        users = User.objects.all()
        profiles = Profile.objects.all()
        faculty_users = User.objects.filter(profile__role='faculty')

        self.stdout.write(f"Users: {users.count()}")
        self.stdout.write(f"Profiles: {profiles.count()}")
        self.stdout.write(f"Faculty users: {faculty_users.count()}")

        if faculty_users.exists():
            self.stdout.write("\nFaculty members:")
            for user in faculty_users:
                self.stdout.write(f"  - {user.username} ({user.get_full_name()})")
        else:
            self.stdout.write(self.style.WARNING("No faculty members found!"))

        self.stdout.write(f"Student groups: {StudentGroup.objects.count()}")
        self.stdout.write(f"Subjects: {Subject.objects.count()}")
        self.stdout.write(f"Timetable entries: {Timetable.objects.count()}")

    def print_backup_summary(self, backup_data):
        """Print summary of backup contents"""
        model_counts = {}
        for item in backup_data:
            model_name = item['model']
            model_counts[model_name] = model_counts.get(model_name, 0) + 1

        self.stdout.write("\nBackup Summary:")
        for model, count in sorted(model_counts.items()):
            self.stdout.write(f"  {model}: {count} objects")

    def list_backups(self):
        """List available backup files"""
        backup_files = [f for f in os.listdir('.') if f.startswith('backup_') and f.endswith('.json')]

        if backup_files:
            self.stdout.write("Available backup files:")
            for backup_file in sorted(backup_files):
                file_size = os.path.getsize(backup_file)
                self.stdout.write(f"  {backup_file} ({file_size} bytes)")
        else:
            self.stdout.write("No backup files found.")
