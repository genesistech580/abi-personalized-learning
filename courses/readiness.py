from assessments.publishing import approved, coverage
from .models import Course


def dsa_readiness():
    course = Course.objects.filter(code="DSA200").first()
    if course is None:
        return {"exists": False}
    first, followup = coverage(course)
    missing = []
    topics = sorted(first.keys() | followup.keys())
    for topic in topics:
        for difficulty in ["foundation", "revision", "intermediate", "advanced"]:
            if not course.resources.filter(status="published", topic__iexact=topic, difficulty=difficulty).exists():
                missing.append(topic + " / " + difficulty)
    return {
        "exists": True,
        "active": course.archived_at is None,
        "lecturer_active": course.lecturer.is_active,
        "topics": len(topics),
        "lessons": course.lessons.filter(status="published").count(),
        "resources": course.resources.filter(status="published").count(),
        "diagnostic_questions": sum(first.values()),
        "followup_questions": sum(followup.values()),
        "matched_coverage": bool(first and first == followup),
        "approved": approved(course),
        "missing_resources": missing,
    }
