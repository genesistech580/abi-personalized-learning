from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import User
from dashboard.forms import CourseForm
from recommendations.services import diagnostic_reviews

from .models import Course, Enrollment, Lesson, LessonCompletion, LessonVisit
from django.utils import timezone


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ("title", "position", "content", "status")


@login_required
def learning_path(request, pk):
    user = request.user
    if user.role == User.Role.STUDENT:
        courses = Course.objects.filter(enrollments__student=user)
    elif user.role == User.Role.LECTURER:
        courses = user.teaching_courses.all()
    else:
        raise PermissionDenied

    course = get_object_or_404(courses, pk=pk)
    lessons = course.lessons.all() if user.role == User.Role.LECTURER else course.lessons.filter(status="published")
    next_lesson = None
    completed_count = 0
    if user.role == User.Role.STUDENT:
        completions = LessonCompletion.objects.filter(lesson=OuterRef("pk"), student=user)
        lessons = list(lessons.annotate(completed=Exists(completions)))
        completed_count = sum(lesson.completed for lesson in lessons)
        next_lesson = next((lesson for lesson in lessons if not lesson.completed), None)

    return render(request, "courses/path.html", {
        "course": course, "lessons": lessons, "next_lesson": next_lesson,
        "completed_count": completed_count,
    })


@login_required
@require_http_methods(["GET", "POST"])
def add_lesson(request, pk):
    if request.user.role != User.Role.LECTURER:
        raise PermissionDenied
    course = get_object_or_404(request.user.teaching_courses, pk=pk)
    form = LessonForm(request.POST if request.method == "POST" else None, initial={"status": "draft"})
    if form.is_valid():
        lesson = form.save(commit=False)
        lesson.course = course
        lesson.save()
        return redirect("learning_path", pk=course.pk)
    return render(request, "courses/add_lesson.html", {"form": form, "course": course})


@login_required
@require_http_methods(["GET", "POST"])
def read_lesson(request, pk):
    user = request.user
    if user.role == User.Role.STUDENT:
        lessons = Lesson.objects.filter(course__enrollments__student=user, status="published")
    elif user.role == User.Role.LECTURER:
        lessons = Lesson.objects.filter(course__lecturer=user)
    else:
        raise PermissionDenied

    lesson = get_object_or_404(lessons.select_related("course"), pk=pk)
    if request.method == "POST":
        if user.role != User.Role.STUDENT:
            raise PermissionDenied
        LessonCompletion.objects.get_or_create(lesson=lesson, student=user)
        return redirect("learning_path", pk=lesson.course_id)

    if user.role == User.Role.STUDENT:
        visit, created = LessonVisit.objects.get_or_create(lesson=lesson, student=user)
        if not created:
            LessonVisit.objects.filter(pk=visit.pk).update(visits=F("visits") + 1, last_opened_at=timezone.now())
        latest = lesson.course.diagnostic_attempts.filter(student=user).order_by("-pk").first()
        if latest and not latest.review_opened and any(
            suggested.pk == lesson.pk
            for suggested, _, _ in diagnostic_reviews(user, course=lesson.course)
        ):
            lesson.course.diagnostic_attempts.filter(pk=latest.pk).update(review_opened=True)

    completed = lesson.completions.filter(student=user).exists()
    return render(request, "courses/lesson.html", {"lesson": lesson, "completed": completed})


class CourseDetailsForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ("code", "title")


@login_required
@require_http_methods(["GET", "POST"])
def manage_course(request, pk, delete=False):
    user = request.user
    if user.role == User.Role.ADMINISTRATOR:
        courses = Course.objects.all()
        form_class = CourseForm
    elif user.role == User.Role.LECTURER:
        courses = user.teaching_courses.all()
        form_class = CourseDetailsForm
    else:
        raise PermissionDenied

    course = get_object_or_404(courses, pk=pk)
    if delete:
        if request.method == "POST":
            course.delete()
            messages.success(request, "Course deleted.")
            return redirect("dashboard")
        return render(request, "courses/delete.html", {"course": course})

    form = form_class(request.POST if request.method == "POST" else None, instance=course)
    if form.is_valid():
        form.save()
        messages.success(request, "Course updated.")
        return redirect("dashboard")
    return render(request, "dashboard/create.html", {"form": form, "title": "Edit course"})


@login_required
@require_POST
def enroll_course(request, pk):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied

    course = get_object_or_404(Course, pk=pk)
    _, created = Enrollment.objects.get_or_create(course=course, student=request.user)
    if created:
        messages.success(request, "You’re enrolled.")
    if course.diagnostic_questions.filter(stage="diagnostic").exists() and not course.diagnostic_attempts.filter(student=request.user).exists():
        return redirect("diagnostic", pk=course.pk)
    return redirect("learning_path", pk=course.pk)

