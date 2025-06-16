from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    # --- ADD THIS METHOD ---
    def ready(self):
        # This imports the signals file so Django can use the signals
        import accounts.signals