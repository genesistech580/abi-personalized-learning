from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.utils import timezone

from assessments.models import Assessment, DiagnosticAttempt, DiagnosticQuestion, Submission
from courses.models import Lesson


def for_student(student):
    now = timezone.now()
    submissions = Submission.objects.filter(assessment=OuterRef("pk"), student=student)
    assessments = (
        Assessment.objects.filter(course__enrollments__student=student)
        .select_related("course")
        .annotate(has_submission=Exists(submissions))
        .filter(has_submission=False)
        .filter(Q(due_at__gte=now) | Q(due_at__isnull=True))
        .order_by(F("due_at").asc(nulls_last=True), "pk")
    )
    recommendations = [
        (assessment, "Complete assessment") for assessment in assessments[:3]
    ]
    remaining = 3 - len(recommendations)
    if remaining:
        recent_grades = (
            Submission.objects.filter(
                student=student,
                score__lt=70,
                assessment__course__enrollments__student=student,
            )
            .select_related("assessment__course")
            .order_by("score", "-updated_at", "pk")
        )
        recommendations.extend(
            (submission.assessment, "Review result") for submission in recent_grades[:remaining]
        )
    return recommendations


def diagnostic_reviews(student, course=None):
    attempts = DiagnosticAttempt.objects.filter(
        student=student, course__enrollments__student=student
    )
    if course is not None:
        attempts = attempts.filter(course=course)
    latest_ids = (
        attempts.filter(course_id=OuterRef("course_id")).order_by("-pk").values("pk")[:1]
    )
    latest = attempts.filter(pk=Subquery(latest_ids)).order_by("-pk")
    results_by_course = {attempt.course_id: attempt.results for attempt in latest}
    questions = DiagnosticQuestion.objects.filter(
        course_id__in=results_by_course, review_lesson__course_id=F("course_id")
    ).select_related("review_lesson__course").order_by("course_id", "pk")
    recommendations = []
    seen = set()
    linked_topics = set()
    for question in questions:
        linked_topics.add((question.course_id, question.topic))
        result = results_by_course[question.course_id].get(question.topic)
        key = (question.topic, question.review_lesson_id)
        if result and result["correct"] < result["total"] and key not in seen:
            recommendations.append((question.review_lesson, question.topic, result))
            seen.add(key)
    for lesson in Lesson.objects.filter(course_id__in=results_by_course).select_related("course"):
        for topic, result in results_by_course[lesson.course_id].items():
            if (lesson.course_id, topic) in linked_topics or topic.casefold() != lesson.title.casefold():
                continue
            if result["correct"] < result["total"]:
                recommendations.append((lesson, topic, result))
    return recommendations
