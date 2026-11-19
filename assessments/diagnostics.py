import hashlib
import json

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.models import User
from courses.models import Course

from recommendations.services import diagnostic_reviews

from .models import DiagnosticAttempt, DiagnosticQuestion
from .publishing import approved


class QuestionForm(forms.ModelForm):
    class Meta:
        model = DiagnosticQuestion
        fields = ("status", "stage", "topic", "prompt", "option_a", "option_b", "option_c", "correct", "explanation", "practice", "review_lesson")


@login_required
@require_http_methods(["GET", "POST"])
def diagnostic(request, pk):
    student = request.user
    if student.role != User.Role.STUDENT:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk, enrollments__student=student)
    stage = request.GET.get("stage", "diagnostic")
    if stage not in {"diagnostic", "followup"}:
        from django.http import Http404
        raise Http404
    questions = list(course.diagnostic_questions.filter(stage=stage, status="published").order_by("pk"))
    payload = [
        (q.pk, q.topic, q.prompt, q.option_a, q.option_b, q.option_c, q.correct)
        for q in questions
    ]
    version = hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()
    form = forms.Form(request.POST if request.method == "POST" else None, initial={"quiz_version": version})
    form.fields["quiz_version"] = forms.CharField(widget=forms.HiddenInput)
    for question in questions:
        form.fields[str(question.pk)] = forms.ChoiceField(
            label=question.prompt,
            choices=(("A", question.option_a), ("B", question.option_b), ("C", question.option_c)),
            widget=forms.RadioSelect,
        )

    if stage == "followup" and not approved(course):
        messages.info(request, "Follow-up quiz is awaiting lecturer review.")
        return redirect("learning_path", pk=course.pk)

    if questions and form.is_valid() and form.cleaned_data["quiz_version"] != version:
        messages.error(request, "The quiz changed. Please try the updated questions.")
        from django.urls import reverse
        return redirect(reverse("diagnostic", args=[course.pk]) + "?stage=" + stage)

    if questions and form.is_bound and not form.errors:
        results = {}
        feedback = []
        for question in questions:
            topic = results.setdefault(question.topic, {"correct": 0, "total": 0})
            topic["total"] += 1
            correct = form.cleaned_data[str(question.pk)] == question.correct
            topic["correct"] += int(correct)
            if not correct:
                feedback.append({
                    "prompt": question.prompt,
                    "explanation": question.explanation,
                    "practice": question.practice,
                    "lesson_id": question.review_lesson_id,
                })
        DiagnosticAttempt.objects.create(
            course=course, student=student, results=results, quiz_version=version,
            stage=stage, comparison_key=(
                course.quiz_approval if approved(course) else ""
            ), question_feedback=feedback,
            question_snapshot=[
                {"topic": q.topic, "prompt": q.prompt, "selected": form.cleaned_data[str(q.pk)],
                 "correct": q.correct, "options": [q.option_a, q.option_b, q.option_c]}
                for q in questions
            ],
        )
        from django.urls import reverse
        return redirect(reverse("diagnostic", args=[course.pk]) + "?stage=" + stage)

    attempts = list(course.diagnostic_attempts.filter(student=student).order_by("-pk")[:10])
    latest = attempts[0] if attempts else None
    review_lessons = diagnostic_reviews(student, course=course)
    return render(request, "assessments/diagnostic.html", {
        "course": course, "form": form, "latest": latest, "has_questions": bool(questions),
        "attempts": attempts, "review_lessons": review_lessons, "stage": stage,
        "has_followup": course.diagnostic_questions.filter(stage="followup").exists(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def add_diagnostic_question(request, pk):
    if request.user.role != User.Role.LECTURER:
        raise PermissionDenied
    course = get_object_or_404(request.user.teaching_courses, pk=pk)
    form = QuestionForm(request.POST if request.method == "POST" else None, initial={"status": "draft"})
    form.fields["review_lesson"].queryset = course.lessons.all()
    if form.is_valid():
        question = form.save(commit=False)
        question.course = course
        question.save()
        return redirect("add_diagnostic_question", pk=course.pk)
    return render(request, "assessments/diagnostic_author.html", {"course": course, "form": form})




