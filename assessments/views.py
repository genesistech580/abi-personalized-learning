from django import forms
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User

from .models import Assessment, Submission


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ("answer",)


@login_required
def submit(request, pk):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied

    assessment = get_object_or_404(
        Assessment, pk=pk, course__enrollments__student=request.user, course__enrollments__withdrawn_at__isnull=True, course__archived_at__isnull=True
    )
    submission = Submission.objects.filter(assessment=assessment, student=request.user).first()
    form = SubmissionForm(request.POST if request.method == "POST" else None, instance=submission)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved, created = Submission.objects.get_or_create(
                assessment=assessment, student=request.user, defaults=form.cleaned_data
            )
            saved = Submission.objects.select_for_update().get(pk=saved.pk)
            if not created:
                if saved.score is not None:
                    messages.error(request, "This submission has been graded.")
                    return redirect("submit_assessment", pk=assessment.pk)
                saved.answer = form.cleaned_data["answer"]
                saved.save(update_fields=["answer", "updated_at"])
        messages.success(request, "Assessment submitted.")
        return redirect("dashboard")

    return render(request, "assessments/submit.html", {
        "assessment": assessment, "form": form, "submission": submission,
    })


class GradeForm(forms.Form):
    score = forms.IntegerField(label="Score (0–100)", min_value=0, max_value=100)
    feedback = forms.CharField(required=False, widget=forms.Textarea)
    submitted_version = forms.DateTimeField(widget=forms.HiddenInput)


@login_required
def review(request, pk):
    if request.user.role != User.Role.LECTURER:
        raise PermissionDenied

    assessment = get_object_or_404(Assessment, pk=pk, course__lecturer=request.user)
    return render(request, "assessments/review.html", {
        "assessment": assessment,
        "submissions": assessment.submissions.select_related("student").order_by("student__username"),
    })


@login_required
def grade(request, pk):
    if request.user.role != User.Role.LECTURER:
        raise PermissionDenied

    submission = get_object_or_404(
        Submission.objects.select_related("assessment", "student"),
        pk=pk,
        assessment__course__lecturer=request.user,
    )
    form = GradeForm(request.POST if request.method == "POST" else None, initial={
        "score": submission.score,
        "feedback": submission.feedback,
        "submitted_version": submission.updated_at.isoformat(),
    })
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = Submission.objects.select_for_update().get(pk=submission.pk)
            if saved.updated_at == form.cleaned_data["submitted_version"]:
                saved.score = form.cleaned_data["score"]
                saved.feedback = form.cleaned_data["feedback"]
                saved.save(update_fields=["score", "feedback", "updated_at"])
                messages.success(request, "Grade saved.")
                return redirect("review_assessment", pk=submission.assessment_id)
        messages.error(request, "The answer changed. Review it again.")
        return redirect("grade_submission", pk=submission.pk)

    return render(request, "assessments/grade.html", {"form": form, "submission": submission})
