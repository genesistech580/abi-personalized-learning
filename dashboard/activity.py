from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, post_delete, m2m_changed


TRACKED_APPS = {"accounts", "courses", "assessments", "dashboard"}


def record_activity(sender, **kwargs):
    # Lesson visits are recorded during page reads and must not cause refresh loops.
    if sender._meta.app_label not in TRACKED_APPS or sender._meta.model_name == "lessonvisit":
        return
    if kwargs.get("raw") or kwargs.get("action", "post_add") not in {"post_add", "post_remove", "post_clear"}:
        return
    transaction.on_commit(
        lambda: (settings.BASE_DIR / ".activity-version").touch(),
        using=kwargs.get("using"),
    )


def connect_activity_signals():
    post_save.connect(record_activity, dispatch_uid="dashboard.activity.save")
    post_delete.connect(record_activity, dispatch_uid="dashboard.activity.delete")
    m2m_changed.connect(record_activity, dispatch_uid="dashboard.activity.m2m")
