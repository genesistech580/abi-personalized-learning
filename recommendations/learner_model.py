"""Enable peer-based ranking only after chronological held-out improvement."""
from collections import defaultdict

from assessments.models import DiagnosticAttempt


def evaluate(course_id):
    histories = {}
    peers = defaultdict(dict)
    errors = []
    learners = set()
    for attempt in DiagnosticAttempt.objects.filter(student__is_demo=False, course_id=course_id).exclude(
        comparison_key=""
    ).order_by("pk"):
        key = (attempt.student_id, attempt.comparison_key)
        first = histories.get(key)
        if first is None:
            histories[key] = attempt
            for topic, result in attempt.results.items():
                peers[(attempt.comparison_key, topic)][attempt.student_id] = result
            continue
        if first is False:
            continue
        histories[key] = False
        for topic, observed in attempt.results.items():
            before = first.results.get(topic)
            others = [
                result for owner, result in peers[(attempt.comparison_key, topic)].items()
                if owner != attempt.student_id
            ]
            total = sum(result["total"] for result in others)
            if not before or not total or not observed["total"]:
                continue
            prior = sum(result["correct"] for result in others) / total
            baseline = before["correct"] / before["total"]
            predicted = (before["correct"] + 2 * prior) / (before["total"] + 2)
            actual = observed["correct"] / observed["total"]
            errors.append((abs(baseline - actual), abs(predicted - actual)))
            learners.add(attempt.student_id)
    enabled = (
        len(errors) >= 10 and len(learners) >= 5
        and sum(model for _, model in errors) < sum(base for base, _ in errors)
    )
    return {"enabled": enabled, "comparisons": len(errors), "learners": len(learners)}


def rank_reviews(student, reviews):
    metrics = {}
    for lesson, topic, result in reviews:
        metrics.setdefault(lesson.course_id, evaluate(lesson.course_id))
    if not any(metric["enabled"] for metric in metrics.values()):
        return reviews

    def priority(item):
        lesson, topic, result = item
        if not metrics[lesson.course_id]["enabled"]:
            return result["correct"] / result["total"]
        values = [
            attempt.results[topic]
            for attempt in DiagnosticAttempt.objects.filter(student__is_demo=False, course=lesson.course)
            .exclude(student=student).order_by("pk")
            if topic in attempt.results
        ]
        total = sum(value["total"] for value in values)
        prior = sum(value["correct"] for value in values) / total if total else .5
        return (result["correct"] + 2 * prior) / (result["total"] + 2)

    return sorted(reviews, key=priority)
