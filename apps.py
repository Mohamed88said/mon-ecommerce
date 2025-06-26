from django.apps import AppConfig

class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        try:
            import store.signals
        except ImportError:
            pass  # Handle the error or log it if needed