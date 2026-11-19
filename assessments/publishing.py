import hashlib
import json
from collections import Counter


def signature(course):
    rows = list(course.diagnostic_questions.filter(status="published").order_by("pk").values_list(
        "pk", "stage", "topic", "prompt", "option_a", "option_b", "option_c", "correct"
    ))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def coverage(course):
    rows = course.diagnostic_questions.filter(status="published")
    first = Counter(rows.filter(stage="diagnostic").values_list("topic", flat=True))
    followup = Counter(rows.filter(stage="followup").values_list("topic", flat=True))
    return first, followup


def approved(course):
    first, followup = coverage(course)
    return bool(first and first == followup and course.quiz_approval == signature(course))
