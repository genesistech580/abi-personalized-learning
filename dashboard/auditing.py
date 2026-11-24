from contextvars import ContextVar
from django.db import transaction
from django.db.models.signals import post_save, pre_save, pre_delete
from django.db.models.deletion import ProtectedError

actor_context = ContextVar("audit_actor", default=None)
TRACKED = {"accounts.user", "courses.course", "courses.enrollment", "courses.lesson", "courses.learningresource",
           "assessments.assessment", "assessments.diagnosticquestion", "assessments.diagnosticattempt",
           "assessments.submission", "assessments.learningfeedback", "assessments.pilotfeedback",
           "dashboard.researchconsent", "dashboard.consentevent"}


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        token = actor_context.set((user.pk, user.username) if user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            actor_context.reset(token)


def before_save(sender, instance, **kwargs):
    if sender._meta.label_lower not in TRACKED or kwargs.get("raw"):
        return
    fields = [f.attname for f in sender._meta.concrete_fields if not f.primary_key and f.name != "last_login"]
    before = sender.objects.filter(pk=instance.pk).values(*fields).first() if instance.pk else None
    instance._audit_fields = [f for f in fields if before is None or before[f] != getattr(instance, f)]


def after_save(sender, instance, created, **kwargs):
    if sender._meta.label_lower not in TRACKED or kwargs.get("raw"):
        return
    fields = getattr(instance, "_audit_fields", [])
    if not fields:
        return
    actor = actor_context.get()
    data = dict(actor_id=actor[0] if actor else None, actor_label=actor[1] if actor else "System",
                action="create" if created else "update", model_label=sender._meta.label_lower,
                object_id=str(instance.pk), fields=fields)
    # Store field names only: no passwords, answers, comments, tokens or personal field values.
    from .models import AuditEvent
    transaction.on_commit(lambda: AuditEvent.objects.create(**data), using=kwargs.get("using"))


def protect_history(sender, instance, **kwargs):
    if sender._meta.label_lower in {"accounts.user", "courses.course", "courses.enrollment",
                                    "assessments.diagnosticattempt", "assessments.submission", "dashboard.auditevent", "dashboard.consentevent"}:
        raise ProtectedError("Archive, deactivate or withdraw this record to preserve learning history.", [instance])


def connect_audit_signals():
    pre_save.connect(before_save, dispatch_uid="audit.before")
    post_save.connect(after_save, dispatch_uid="audit.after")
    pre_delete.connect(protect_history, dispatch_uid="audit.protect")
