"""Transparent topic-level recommendations from the agreed five performance bands."""
from assessments.models import DiagnosticAttempt
from assessments.publishing import approved
from courses.models import LearningResource, ResourceProgress

# Initial supervisor-reviewable thresholds from the supplied workflow.
BANDS = [
    (85, "Excellent", "advanced", "Try advanced exercises or extension activities."),
    (70, "Good", "intermediate", "Build understanding with intermediate exercises."),
    (50, "Average", "revision", "Revise the topic and practise more questions."),
    (40, "Below average", "foundation", "Review foundational explanations and guided practice."),
    (0, "Poor", "foundation", "Start with introductory material and remedial exercises."),
]


def classify(correct, total):
    if total <= 0:
        return None
    score = 100 * correct / total
    for minimum, label, difficulty, advice in BANDS:
        if score >= minimum:
            return {"score": score, "category": label, "difficulty": difficulty, "advice": advice}


def normalize(topic):
    normalized = " ".join(topic.casefold().split())
    return "searching and sorting" if normalized == "searching and sorting algorithms" else normalized


def topic_plan(student, course, through=None):
    attempts = DiagnosticAttempt.objects.filter(student=student, course=course)
    if through is not None:
        attempts = attempts.filter(pk__lte=through)
    history = list(attempts.order_by("pk"))
    if not history:
        return {"course": course, "topics": [], "needs_diagnostic": True, "followup_ready": False}
    latest = history[-1]
    first = next((attempt for attempt in history if latest.comparison_key and attempt.comparison_key == latest.comparison_key and attempt.stage == "diagnostic" and attempt.pk < latest.pk), None)
    comparable = first if latest.stage == "followup" else None
    resources = list(course.resources.filter(status="published"))
    done = set(ResourceProgress.objects.filter(student=student, resource__course=course, completed_at__isnull=False).values_list("resource_id", flat=True))
    topics = []
    for name, result in latest.results.items():
        band = classify(result["correct"], result["total"])
        if not band:
            continue
        prior = comparable.results.get(name) if comparable else None
        prior_score = 100 * prior["correct"] / prior["total"] if prior and prior["total"] else None
        matching = [resource for resource in resources if normalize(resource.topic) == normalize(name) and resource.difficulty == band["difficulty"]]
        priority = {"notes": 0, "practice": 1, "example": 2, "video": 3} if band["category"] == "Poor" else {"example": 0, "practice": 1, "notes": 2, "video": 3}
        comparable_history = [attempt for attempt in history if latest.comparison_key and attempt.comparison_key == latest.comparison_key and name in attempt.results and attempt.results[name]["total"]]
        series = [{"score": 100 * attempt.results[name]["correct"] / attempt.results[name]["total"], "stage": attempt.stage, "date": attempt.submitted_at, "label": str(number+1)} for number, attempt in enumerate(comparable_history)]
        reason = "Resources match your latest topic score."
        recent = [item["score"] for item in series[-3:]]
        if len(recent) >= 2:
            if recent[-1] > recent[-2]:
                reason = "Your comparable topic score increased; the resource level follows your latest result."
            elif recent[-1] < 70 and recent[-2] < 70:
                reason = "Repeated results remain below 70%; extra foundational support has been added."
                extra = [item for item in resources if normalize(item.topic) == normalize(name) and item.difficulty == "foundation" and item.kind in {"example", "practice"} and item not in matching]
                matching.extend(extra[:2])
        matching.sort(key=lambda item: (item.pk in done, item.difficulty != band["difficulty"], priority.get(item.kind, 4)))
        target = [item for item in matching if item.difficulty == band["difficulty"]]
        all_done = bool(target) and all(item.pk in done for item in target)
        if all_done:
            reason += " Your matching activities are complete; use the follow-up quiz to check your understanding."
        visible_series = series[-8:]
        chart_points = [{**item, "x": 45 + number * (500 / max(1, len(visible_series)-1)), "y": 140 - item["score"] * 1.15} for number, item in enumerate(visible_series)]
        chart_line = " ".join(f"{item['x']:.1f},{item['y']:.1f}" for item in chart_points)
        # A topic-specific published lesson remains a useful fallback if tagged resources are absent.
        lessons = list(course.lessons.filter(status="published", diagnostic_questions__topic__iexact=name).distinct()) if not matching else []
        topics.append({"name": name, **band, "previous": prior_score,
            "change": band["score"] - prior_score if prior_score is not None else None,
            "reason": reason, "all_done": all_done, "series": chart_points, "chart_line": chart_line,
            "resources": [{"item": item, "completed": item.pk in done} for item in matching], "lessons": lessons})
    topics.sort(key=lambda item: (item["score"], item["name"].casefold()))
    return {"course": course, "topics": topics, "attempt": latest, "attempt_count": len(history),
            "needs_diagnostic": False, "followup_ready": approved(course) and any(attempt.stage == "diagnostic" for attempt in history)}


def learning_plans(student):
    courses = student.enrollments.filter(withdrawn_at__isnull=True, course__archived_at__isnull=True).select_related("course").order_by("course__code")
    return [topic_plan(student, enrollment.course) for enrollment in courses]
