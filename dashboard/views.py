from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Subquery
from django.shortcuts import redirect, render

from accounts.models import User
from assessments.models import Assessment, DiagnosticAttempt, LearningFeedback, Submission
from courses.models import Course, Enrollment, Lesson, LessonCompletion
from recommendations.services import diagnostic_reviews, for_student

from .forms import AssessmentForm, CourseForm, EnrollmentForm, LecturerForm


ADMIN_ACTIONS = (
    ("add_lecturer", "Add lecturer"),
    ("add_course", "Add course"),
    ("add_enrollment", "Enroll student"),
    ("add_assessment", "Add assessment"),
)


@login_required
def index(request):
    user = request.user
    context = {}
    if user.role == User.Role.STUDENT:
        section = request.GET.get("section", "overview")
        if section not in {"overview", "courses", "catalog", "assessments", "recommended", "performance"}:
            return redirect("dashboard")
        context["section"] = section
        context["lecturer_feedback"] = LearningFeedback.objects.filter(student=user, course__enrollments__student=user).select_related("course", "lesson").order_by("-pk")[:20]
        if section == "performance":
            attempts = DiagnosticAttempt.objects.filter(
                student=user, course__enrollments__student=user
            ).select_related("course").order_by("-pk")
            by_course = {}
            for attempt in attempts:
                history = by_course.setdefault(attempt.course_id, [])
                if len(history) < 2:
                    history.append(attempt)

            reviews_by_course = {}
            for lesson, topic, result in diagnostic_reviews(user):
                reviews_by_course.setdefault(lesson.course_id, {}).setdefault(topic, []).append(lesson)

            reports = []
            for history in by_course.values():
                latest = history[0]
                previous = history[1].results if len(history) > 1 else {}
                topics = []
                for topic, result in latest.results.items():
                    prior = previous.get(topic)
                    topics.append({
                        "name": topic,
                        "result": result,
                        "previous": prior if prior and prior["total"] == result["total"] else None,
                        "lessons": reviews_by_course.get(latest.course_id, {}).get(topic, []),
                    })
                reports.append({"attempt": latest, "topics": topics})
            context["reports"] = reports
            return render(request, "dashboard/student.html", context)
        if section in {"overview", "recommended"}:
            context["diagnostic_reviews"] = diagnostic_reviews(user)
        if section == "recommended":
            context["diagnostic_courses"] = Course.objects.filter(
                enrollments__student=user, diagnostic_questions__isnull=False
            ).distinct().order_by("code")
        context["quiz_courses"] = Course.objects.filter(
            enrollments__student=user, diagnostic_questions__isnull=False
        ).distinct().order_by("code")
        context["course_heading"] = "My courses"
        context["recommendations"] = for_student(user)
        enrollments = Enrollment.objects.filter(course=OuterRef("pk"), student=user)
        context["course_catalog"] = (
            Course.objects.select_related("lecturer")
            .annotate(enrolled=Exists(enrollments), lesson_count=Count("lessons"))
            .order_by("code")
        )
        submissions = Submission.objects.filter(assessment=OuterRef("pk"), student=user)
        context["student_assessments"] = (
            Assessment.objects.filter(course__enrollments__student=user)
            .select_related("course")
            .annotate(
                submission_id=Subquery(submissions.values("pk")[:1]),
                score=Subquery(submissions.values("score")[:1]),
            )
            .order_by("course__code", "title", "pk")
        )
        completions = LessonCompletion.objects.filter(lesson=OuterRef("pk"), student=user)
        lessons = Lesson.objects.filter(status="published").annotate(completed=Exists(completions))
        courses = Course.objects.filter(enrollments__student=user).prefetch_related(
            Prefetch("lessons", queryset=lessons, to_attr="learning_lessons")
        )
    elif user.role == User.Role.LECTURER:
        section = request.GET.get("section", "overview")
        if section not in {"overview", "courses", "assessments", "insights"}:
            return redirect("dashboard")
        courses = user.teaching_courses.order_by("code")
        assessments = Assessment.objects.filter(course__lecturer=user)
        context = {"section": section}
        if section == "overview":
            context.update(
                course_count=courses.count(),
                assessment_count=assessments.count(),
                pending_count=Submission.objects.filter(
                    assessment__course__lecturer=user, score__isnull=True
                ).count(),
            )
        elif section == "courses":
            context["courses"] = courses
        elif section == "insights":
            attempts = DiagnosticAttempt.objects.filter(
                course__lecturer=user,
                course__enrollments__student_id=F("student_id"),
            )
            latest_ids = attempts.filter(
                course_id=OuterRef("course_id"), student_id=OuterRef("student_id")
            ).order_by("-pk").values("pk")[:1]
            summaries = {}
            for attempt in attempts.filter(pk=Subquery(latest_ids)):
                topics = summaries.setdefault(attempt.course_id, {})
                for name, result in attempt.results.items():
                    totals = topics.setdefault(name, {"students": 0, "review": 0})
                    totals["students"] += 1
                    totals["review"] += int(result["correct"] < result["total"])
            context["insights"] = [
                (course, sorted(
                    summaries.get(course.pk, {}).items(),
                    key=lambda topic: (-topic[1]["review"], topic[0].casefold()),
                ))
                for course in courses
            ]
        else:
            context["assessments"] = assessments.select_related("course").order_by(
                "course__code", "title", "pk"
            )
        return render(request, "dashboard/lecturer.html", context)
    else:
        section = request.GET.get("section", "overview")
        if section not in {"overview", "courses", "people", "enrollments", "pilot"}:
            return redirect("dashboard")
        context["section"] = section
        context["lecturer_feedback"] = LearningFeedback.objects.filter(student=user, course__enrollments__student=user).select_related("course", "lesson").order_by("-pk")[:20]
        if section == "pilot":
            learner_attempts = DiagnosticAttempt.objects.filter(
                course__enrollments__student_id=F("student_id")
            ).values("course_id", "student_id").annotate(attempt_count=Count("pk"))
            summaries = {}
            for row in learner_attempts:
                summary = summaries.setdefault(
                    row["course_id"], {"started": 0, "retook": 0, "attempts": 0}
                )
                summary["started"] += 1
                summary["retook"] += int(row["attempt_count"] > 1)
                summary["attempts"] += row["attempt_count"]
            courses_with_quizzes = Course.objects.filter(
                diagnostic_questions__isnull=False
            ).distinct().order_by("code")
            context["pilot_activity"] = [
                (course, summaries.get(course.pk, {"started": 0, "retook": 0, "attempts": 0}))
                for course in courses_with_quizzes
            ]
            return render(request, "dashboard/index.html", context)
        context["actions"] = ADMIN_ACTIONS
        context["enrollments"] = Enrollment.objects.select_related("course", "student").order_by(
            "course__code", "student__username"
        )
        students = User.objects.filter(role=User.Role.STUDENT).order_by("username")
        lecturers = (
            User.objects.filter(role=User.Role.LECTURER)
            .annotate(student_count=Count("teaching_courses__enrollments__student", distinct=True))
            .order_by("username")
        )
        courses = Course.objects.all()
        context.update(
            students=students.annotate(course_count=Count("enrollments")),
            lecturers=lecturers,
            student_total=students.count(),
            lecturer_total=lecturers.count(),
            course_total=courses.count(),
            enrollment_total=context["enrollments"].count(),
        )

    context["courses"] = courses.select_related("lecturer").prefetch_related("assessments").order_by("code")
    if user.role == User.Role.STUDENT:
        context["course_progress"] = [
            (course, sum(lesson.completed for lesson in course.learning_lessons))
            for course in context["courses"]
        ]
        for course, completed_count in context["course_progress"]:
            next_lesson = next(
                (lesson for lesson in course.learning_lessons if not lesson.completed), None
            )
            if next_lesson:
                context.update(
                    featured_course=course,
                    next_lesson=next_lesson,
                    completed_count=completed_count,
                )
                break
        return render(request, "dashboard/student.html", context)
    return render(request, "dashboard/index.html", context)


@login_required
def create_record(request, form_class, title, success_message):
    user = request.user
    lecturer_assessment = user.role == User.Role.LECTURER and form_class is AssessmentForm
    if user.role != User.Role.ADMINISTRATOR and not lecturer_assessment:
        raise PermissionDenied

    form = form_class(request.POST if request.method == "POST" else None, request.FILES)
    if lecturer_assessment:
        form.fields["course"].queryset = user.teaching_courses.order_by("code")

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, success_message)
        return redirect("dashboard")

    return render(request, "dashboard/create.html", {"form": form, "title": title})













