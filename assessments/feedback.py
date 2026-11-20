from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from accounts.models import User
from courses.models import Course
from dashboard.models import ResearchConsent
from .models import DiagnosticAttempt, PilotFeedback


class FeedbackForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.none())
    RATINGS = [(value, value) for value in range(1, 6)]
    ease = forms.TypedChoiceField(choices=RATINGS, coerce=int, label="Ease of use")
    clarity = forms.TypedChoiceField(choices=RATINGS, coerce=int, label="Clarity of recommendations")
    usefulness = forms.TypedChoiceField(choices=RATINGS, coerce=int, label="Helpfulness for learning")


@login_required
@require_http_methods(["GET", "POST"])
def pilot_feedback(request):
    if request.user.role == User.Role.ADMINISTRATOR:
        return redirect("admin_evaluation")
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    consent = ResearchConsent.objects.filter(student=request.user, consented_at__isnull=False, withdrawn_at__isnull=True).first()
    courses = Course.objects.filter(enrollments__student=request.user, enrollments__withdrawn_at__isnull=True, archived_at__isnull=True,
        diagnostic_attempts__student=request.user).distinct().order_by("code")
    form = FeedbackForm(request.POST if request.method == "POST" else None)
    form.fields["course"].queryset = courses
    eligible = bool(consent and courses.exists())
    if request.method == "POST":
        if not eligible:
            raise PermissionDenied
        if form.is_valid():
            data = form.cleaned_data.copy()
            course = data.pop("course")
            PilotFeedback.objects.update_or_create(student=request.user, course=course, defaults=data)
            messages.success(request, "Feedback saved.")
            return redirect("pilot_feedback")
    return render(request, "assessments/pilot_feedback.html", {"form": form, "eligible": eligible})
