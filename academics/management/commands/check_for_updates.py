import subprocess
from django.core.cache import cache
from django.core.management.base import BaseCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Checks for new commits in the remote git repository and caches the count.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking for application updates...")

        try:
            # First, fetch the latest data from the remote repository
            subprocess.run(['git', 'fetch'], check=True)

            # Compare the local HEAD with the remote main/master branch
            # This command counts the number of commits that are in 'origin/main' but not in the local 'HEAD'
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD..origin/main'],
                capture_output=True,
                text=True,
                check=True
            )

            # The output will be a number (as a string), so we convert it to an integer
            update_count = int(result.stdout.strip())

            # Store the result in Django's cache for 1 hour
            cache.set('git_update_count', update_count, 3600)

            self.stdout.write(self.style.SUCCESS(f"Found {update_count} available updates."))

        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            # If git commands fail, assume 0 updates and log the error
            logger.error(f"Error checking for git updates: {e}")
            cache.set('git_update_count', 0, 3600)  # Cache 0 to prevent repeated errors
            self.stderr.write(self.style.ERROR(f"Could not check for updates. Error: {e}"))
