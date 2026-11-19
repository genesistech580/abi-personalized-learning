from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.shortcuts import render

from accounts.models import User
from courses.models import Course

from .models import DiagnosticAttempt


def summarize(pairs):
    count = len(pairs)
    if not count:
        return None
    first = sum(before for before, _ in pairs) / count
    last = sum(after for _, after in pairs) / count
    return {"count": count, "first": first, "last": last, "change": last - first}


@login_required
def outcomes(request):
    user = request.user
    attempts = DiagnosticAttempt.objects.filter(course__enrollments__student_id=F("student_id"))
    if user.role == User.Role.STUDENT:
        attempts = attempts.filter(student=user)
    elif user.role == User.Role.LECTURER:
        attempts = attempts.filter(course__lecturer=user)
    elif user.role != User.Role.ADMINISTRATOR:
        raise PermissionDenied

    histories = {}
    for attempt in attempts.order_by("pk"):
        histories.setdefault(attempt.course_id, {}).setdefault(attempt.student_id, []).append(attempt)

    reports = []
    for course in Course.objects.filter(pk__in=histories).order_by("code"):
        pairs = []
        topic_pairs = {}
        review_topics = {}
        review_count = 0
        for history in histories[course.pk].values():
            latest = history[-1]
            for topic, result in latest.results.items():
                if result["correct"] < result["total"]:
                    review_topics[topic] = review_topics.get(topic, 0) + 1
            if not latest.quiz_version:
                continue
            comparable = [attempt for attempt in history if attempt.quiz_version == latest.quiz_version]
            if len(comparable) < 2:
                continue
            first = comparable[0]
            if not first.question_count or not latest.question_count:
                continue
            pairs.append((100 * first.correct_count / first.question_count,
                          100 * latest.correct_count / latest.question_count))
            review_count += any(attempt.review_opened for attempt in history if first.pk <= attempt.pk < latest.pk)
            for topic, result in latest.results.items():
                before = first.results[topic]
                topic_pairs.setdefault(topic, []).append((
                    100 * before["correct"] / before["total"],
                    100 * result["correct"] / result["total"],
                ))
        reports.append({
            "course": course,
            "overall": summarize(pairs),
            "review_count": review_count,
            "topics": [
                (topic, summarize(topic_pairs.get(topic, [])), review_topics.get(topic, 0))
                for topic in sorted(topic_pairs.keys() | review_topics.keys(), key=str.casefold)
            ],
        })

    return render(request, "assessments/outcomes.html", {"reports": reports})
