from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count
from django.shortcuts import render

from accounts.models import User

from recommendations.learner_model import evaluate
from courses.models import Course

from .models import DiagnosticAttempt, PilotFeedback


@login_required
def pilot_evaluation(request):
    if request.user.role != User.Role.ADMINISTRATOR:
        raise PermissionDenied

    attempts = DiagnosticAttempt.objects.filter(student__is_demo=False, 
        course__code="PILOT-JAVA"
    ).exclude(quiz_version="").order_by("pk")
    first_results = {}
    evaluated = set()
    peer_totals = defaultdict(dict)
    score_changes = []
    errors = []
    for attempt in attempts:
        key = (attempt.student_id, attempt.quiz_version)
        if key not in first_results:
            first_results[key] = attempt
            for topic, result in attempt.results.items():
                peer_totals[(attempt.quiz_version, topic)][attempt.student_id] = result
            continue
        if key in evaluated:
            continue
        evaluated.add(key)
        first = first_results[key]
        if first.question_count and attempt.question_count:
            score_changes.append(100 * (
                attempt.correct_count / attempt.question_count
                - first.correct_count / first.question_count
            ))
        for topic, result in attempt.results.items():
            previous = first.results.get(topic)
            peers = [
                value for student_id, value in peer_totals[(attempt.quiz_version, topic)].items()
                if student_id != attempt.student_id
            ]
            if not previous or not previous["total"] or not result["total"] or not peers:
                continue
            peer_correct = sum(peer["correct"] for peer in peers)
            peer_total = sum(peer["total"] for peer in peers)
            if not peer_total:
                continue
            baseline = previous["correct"] / previous["total"]
            peer_rate = peer_correct / peer_total
            predicted = (previous["correct"] + 2 * peer_rate) / (previous["total"] + 2)
            observed = result["correct"] / result["total"]
            errors.append((abs(baseline - observed), abs(predicted - observed)))

    pilot = Course.objects.filter(code="PILOT-JAVA").first()
    model_status = evaluate(pilot.pk) if pilot else None
    feedback = PilotFeedback.objects.aggregate(
        count=Count("pk"), ease=Avg("ease"), clarity=Avg("clarity"), usefulness=Avg("usefulness")
    )
    return render(request, "assessments/evaluation.html", {
        "feedback": feedback, "model_status": model_status,
        "pair_count": len(score_changes),
        "score_change": sum(score_changes) / len(score_changes) if score_changes else None,
        "prediction_count": len(errors),
        "baseline_error": 100 * sum(baseline for baseline, _ in errors) / len(errors) if errors else None,
        "model_error": 100 * sum(model for _, model in errors) / len(errors) if errors else None,
    })

