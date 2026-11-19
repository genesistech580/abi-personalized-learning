from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User

from .models import DiagnosticAttempt, PilotFeedback


class FeedbackForm(forms.Form):
    RATINGS = [(value, value) for value in range(1, 6)]
    ease = forms.TypedChoiceField(choices=RATINGS, coerce=int, label="Ease of use")
    clarity = forms.TypedChoiceField(choices=RATINGS, coerce=int, label="Clarity of recommendations")
    usefulness = forms.TypedChoiceField(choices=RATINGS, coerce=int, label="Helpfulness for learning")


@login_required
@require_http_methods(["GET", "POST"])
def pilot_feedback(request):
    user = request.user
    if user.role == User.Role.ADMINISTRATOR:
        if request.method != "GET":
            raise PermissionDenied
        summary = PilotFeedback.objects.aggregate(
            count=Count("pk"), ease=Avg("ease"), clarity=Avg("clarity"), usefulness=Avg("usefulness")
        )
        return render(request, "assessments/pilot_feedback.html", {"summary": summary})

    if user.role != User.Role.STUDENT:
        raise PermissionDenied
    eligible = DiagnosticAttempt.objects.filter(
        student=user, course__code="PILOT-JAVA", course__enrollments__student=user
    ).exists()
    saved = PilotFeedback.objects.filter(student=user).values("ease", "clarity", "usefulness").first()
    form = FeedbackForm(request.POST if request.method == "POST" else None, initial=saved)
    if request.method == "POST":
        if not eligible:
            raise PermissionDenied
        if form.is_valid():
            PilotFeedback.objects.update_or_create(student=user, defaults=form.cleaned_data)
            messages.success(request, "Feedback saved.")
            return redirect("pilot_feedback")
    return render(request, "assessments/pilot_feedback.html", {"form": form, "eligible": eligible})
