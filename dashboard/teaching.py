from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.models import User
from assessments.diagnostics import QuestionForm
from assessments.models import DiagnosticAttempt, LearningFeedback, Submission
from assessments.publishing import approved, coverage, signature
from courses.models import Course, Lesson, LessonCompletion, ResourceProgress
from recommendations.plans import topic_plan
from courses.views import LessonForm


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = LearningFeedback
        fields = ("topic", "comment", "lesson")


class ApprovalForm(forms.Form):
    comparable = forms.BooleanField(label="I reviewed both quizzes and confirm comparable difficulty.")
    version = forms.CharField(widget=forms.HiddenInput)


@login_required
@require_http_methods(["GET", "POST"])
def teaching(request, pk=None, student_id=None):
    if request.user.role not in {User.Role.LECTURER, User.Role.ADMINISTRATOR}:
        raise PermissionDenied
    is_admin = request.user.role == User.Role.ADMINISTRATOR
    if is_admin and request.method != "GET":
        raise PermissionDenied
    courses = Course.objects.order_by("code") if is_admin else request.user.teaching_courses.order_by("code")
    context = {"courses": courses, "is_admin": is_admin}
    if pk is None:
        return render(request, "dashboard/teaching.html", context)
    course = get_object_or_404(courses, pk=pk)
    context["course"] = course
    roster = course.enrollments.select_related("student").order_by("student__username")
    lessons = course.lessons.filter(status="published")
    context["lesson_count"] = lessons.count()
    rows = []
    for enrollment in roster:
        student = enrollment.student
        attempts = list(course.diagnostic_attempts.filter(student=student).order_by("pk"))
        completed = LessonCompletion.objects.filter(student=student, lesson__in=lessons).count()
        pending = course.assessments.exclude(submissions__student=student).count()
        latest = attempts[-1] if attempts else None
        change = None
        if latest and latest.stage == "followup" and latest.comparison_key:
            first = next((attempt for attempt in attempts if attempt.stage == "diagnostic" and attempt.comparison_key == latest.comparison_key and attempt.pk < latest.pk), None)
            if first and first.pk != latest.pk and first.question_count and latest.question_count:
                change = 100 * (latest.correct_count / latest.question_count - first.correct_count / first.question_count)
        rows.append({"student": student, "completed": completed, "attempts": len(attempts),
                     "pending": pending, "change": change})
    context["roster"] = rows
    if student_id is not None:
        enrollment = get_object_or_404(roster, student_id=student_id)
        student = enrollment.student
        attempts = list(course.diagnostic_attempts.filter(student=student).order_by("-pk"))
        context.update(
            learner=student, attempts=attempts,
            enrollment=enrollment,
            topic_profile=topic_plan(student, course),
            resource_activity=ResourceProgress.objects.filter(student=student, resource__course=course).select_related("resource").order_by("-last_opened_at"),
            lesson_states=[(lesson, LessonCompletion.objects.filter(student=student, lesson=lesson).first()) for lesson in course.lessons.all()],
            completions=LessonCompletion.objects.filter(student=student, lesson__course=course).select_related("lesson"),
            comments=LearningFeedback.objects.filter(student=student, course=course).select_related("lesson").order_by("-pk"),
            weak_topics=[
                name for name, result in attempts[0].results.items()
                if result["correct"] * 100 < 70 * result["total"]
            ] if attempts else [],
        )
        form = FeedbackForm(request.POST if request.method == "POST" else None)
        form.fields["lesson"].queryset = lessons
        if request.method == "POST" and form.is_valid():
            feedback = form.save(commit=False)
            feedback.student = student
            feedback.course = course
            feedback.lecturer = request.user
            feedback.save()
            messages.success(request, "Feedback sent.")
            return redirect("student_detail", pk=course.pk, student_id=student.pk)
        context["form"] = None if is_admin else form
    return render(request, "dashboard/teaching.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def edit_content(request, kind, pk):
    if request.user.role not in {User.Role.LECTURER, User.Role.ADMINISTRATOR}:
        raise PermissionDenied
    scope = {} if request.user.role == User.Role.ADMINISTRATOR else {"course__lecturer": request.user}
    if kind == "lesson":
        item = get_object_or_404(Lesson, pk=pk, **scope)
        form_class = LessonForm
    elif kind == "question":
        from assessments.models import DiagnosticQuestion
        item = get_object_or_404(DiagnosticQuestion, pk=pk, **scope)
        form_class = QuestionForm
    else:
        raise PermissionDenied
    form = form_class(request.POST if request.method == "POST" else None, instance=item)
    if kind == "question":
        form.fields["review_lesson"].queryset = item.course.lessons.filter(status="published")
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Content saved.")
        return redirect("content_preview", kind=kind, pk=item.pk)
    return render(request, "dashboard/create.html", {"form": form, "title": "Edit " + kind})


@login_required
def content_preview(request, kind, pk):
    if request.user.role not in {User.Role.LECTURER, User.Role.ADMINISTRATOR}:
        raise PermissionDenied
    scope = {} if request.user.role == User.Role.ADMINISTRATOR else {"course__lecturer": request.user}
    if kind == "lesson":
        item = get_object_or_404(Lesson, pk=pk, **scope)
    else:
        from assessments.models import DiagnosticQuestion
        item = get_object_or_404(DiagnosticQuestion, pk=pk, **scope)
    return render(request, "dashboard/content_preview.html", {"item": item, "kind": kind})


@login_required
@require_http_methods(["GET", "POST"])
def publish_check(request, pk):
    if request.user.role != User.Role.LECTURER:
        raise PermissionDenied
    course = get_object_or_404(Course, pk=pk, lecturer=request.user)
    first, followup = coverage(course)
    matched = bool(first and first == followup)
    form = ApprovalForm(request.POST if request.method == "POST" else None, initial={"version": signature(course)})
    if request.method == "POST" and form.is_valid():
        if not matched:
            form.add_error(None, "Match the published topic counts before approval.")
        elif form.cleaned_data["version"] != signature(course):
            form.add_error(None, "Questions changed. Review again.")
        else:
            course.quiz_approval = signature(course)
            course.save(update_fields=["quiz_approval"])
            messages.success(request, "Follow-up quiz approved.")
            return redirect("publish_check", pk=course.pk)
    topics = sorted(first.keys() | followup.keys())
    return render(request, "dashboard/publish_check.html", {
        "course": course, "form": form, "matched": matched, "approved": approved(course),
        "coverage": [(topic, first[topic], followup[topic]) for topic in topics],
        "questions": course.diagnostic_questions.filter(status="published"),
    })

