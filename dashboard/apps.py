from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        from .activity import connect_activity_signals
        connect_activity_signals()
        from .auditing import connect_audit_signals
        connect_audit_signals()
