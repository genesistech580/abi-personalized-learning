from django.conf import settings
from django.db import models


class ResearchConsent(models.Model):
    study = models.ForeignKey("PilotStudy", null=True, blank=True, on_delete=models.SET_NULL)

    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    cohort = models.CharField(max_length=80, blank=True)
    information_version = models.CharField(max_length=20, default="2026-11-19")
    consented_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    @property
    def active(self):
        return bool(self.consented_at and not self.withdrawn_at)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20)
    model_label = models.CharField(max_length=100)
    object_id = models.CharField(max_length=80)
    fields = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class ConsentEvent(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=12, choices=[("consent", "Consented"), ("withdraw", "Withdrawn")])
    information_version = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")


class ServiceStatus(models.Model):
    service = models.CharField(max_length=20, unique=True)
    successful = models.BooleanField()
    summary = models.CharField(max_length=160)
    checked_at = models.DateTimeField(auto_now=True)


class PilotStudy(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.PROTECT, related_name="pilot_studies")
    title = models.CharField(max_length=200)
    group_code = models.CharField(max_length=80, unique=True)
    target_participants = models.PositiveSmallIntegerField(default=20)
    approval_note = models.TextField(blank=True)
    approval_recorded_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
