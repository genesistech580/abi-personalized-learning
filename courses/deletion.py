"""Explicit administrator-only permanent deletion, scoped to a single course."""
import logging
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from assessments.models import DiagnosticAttempt, Submission, PilotFeedback
from dashboard.auditing import permanent_delete_scope
from dashboard.models import AuditEvent
from .models import Course, Enrollment, LearningResource, ResourceProgress

logger = logging.getLogger(__name__)


def course_delete_counts(course):
    return {
        "Lessons": course.lessons.count(), "Resources": course.resources.count(),
        "Enrollments": course.enrollments.count(), "Quiz questions": course.diagnostic_questions.count(),
        "Quiz attempts": course.diagnostic_attempts.count(), "Assessments": course.assessments.count(),
        "Submissions": Submission.objects.filter(assessment__course=course).count(),
        "Survey responses": PilotFeedback.objects.filter(course=course).count(),
    }


@transaction.atomic
def permanently_delete_course(course_id, actor):
    if not actor.is_authenticated or not actor.is_active or actor.role != "administrator":
        raise PermissionDenied
    course = Course.objects.select_for_update().get(pk=course_id)
    resources = list(course.resources.all())
    files = [(item.attachment.storage, item.attachment.name) for item in resources if item.attachment]
    scope = {("courses.course", course.pk)}
    for model, query in [
        (Enrollment, Enrollment.objects.filter(course=course)),
        (DiagnosticAttempt, DiagnosticAttempt.objects.filter(course=course)),
        (Submission, Submission.objects.filter(assessment__course=course)),
    ]:
        scope.update((model._meta.label_lower, pk) for pk in query.values_list("pk", flat=True))
    token = permanent_delete_scope.set(frozenset(scope))
    try:
        # Remove explicit PROTECT dependents before the remaining course cascade.
        ResourceProgress.objects.filter(resource__course=course).delete()
        PilotFeedback.objects.filter(course=course).delete()
        LearningResource.objects.filter(course=course).delete()
        AuditEvent.objects.create(actor=actor, actor_label=actor.username, action="delete",
            model_label="courses.course", object_id=str(course.pk),
            fields=["permanent_course_deletion", "related_learning_records"])
        models.Model.delete(course)
    finally:
        permanent_delete_scope.reset(token)

    def remove_files():
        for storage, name in files:
            if not LearningResource.objects.filter(attachment=name).exists():
                try:
                    storage.delete(name)
                except OSError:
                    logger.warning("A deleted course attachment could not be removed from private storage.")
    transaction.on_commit(remove_files)
