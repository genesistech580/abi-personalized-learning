from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, OuterRef, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from assessments.models import DiagnosticAttempt, Submission
from courses.models import Course, LessonCompletion
from recommendations.services import diagnostic_reviews


from .services import record_service
from .chat import course_reply, ChatError, chat_configuration, chat_mode


class ChatForm(forms.Form):
    message = forms.CharField(
        max_length=1000, widget=forms.Textarea(attrs={"rows": 3}), label="Message"
    )


@login_required
def learning_assistant(request):
    user = request.user
    if user.role == User.Role.STUDENT:
        courses = Course.objects.filter(enrollments__student=user, enrollments__withdrawn_at__isnull=True, archived_at__isnull=True)
    elif user.role == User.Role.LECTURER:
        courses = user.teaching_courses.all()
    else:
        raise PermissionDenied

    courses = courses.order_by("code")
    course_id = request.GET.get("course")
    if course_id is not None and (not course_id.isdecimal() or len(course_id) > 18):
        raise Http404
    course = get_object_or_404(courses, pk=course_id) if course_id else courses.first()
    context = {"courses": courses, "course": course, "guidance_requested": course_id is not None}
    if course and user.role == User.Role.STUDENT:
        completions = LessonCompletion.objects.filter(lesson=OuterRef("pk"), student=user)
        context.update(
            reviews=diagnostic_reviews(user, course=course),
            tried_quiz=course.diagnostic_attempts.filter(student=user).exists(),
            has_quiz=course.diagnostic_questions.exists(),
            next_lesson=course.lessons.filter(status="published").annotate(done=Exists(completions)).filter(done=False).first(),
        )
    elif course:
        attempts = DiagnosticAttempt.objects.filter(
            course=course, course__enrollments__student_id=F("student_id")
        )
        latest_ids = attempts.filter(student_id=OuterRef("student_id")).order_by("-pk").values("pk")[:1]
        latest_attempts = list(attempts.filter(pk=Subquery(latest_ids)))
        topics = {}
        for attempt in latest_attempts:
            for name, result in attempt.results.items():
                if result["correct"] * 100 < 70 * result["total"]:
                    topics[name] = topics.get(name, 0) + 1
        context.update(
            diagnostic_participants=len(latest_attempts),
            review_topics=sorted(topics.items(), key=lambda topic: (-topic[1], topic[0].casefold()))[:3],
            pending=Submission.objects.filter(assessment__course=course, score__isnull=True).count(),
            has_quiz=course.diagnostic_questions.exists(),
        )
    if course:
        chat_key = f"course-chat:{course.pk}"
        history = request.session.get(chat_key, [])
        if not isinstance(history, list):
            history = []
        history = [item for item in history[-12:] if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str)]
        form = ChatForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and request.POST.get("action") == "clear":
            request.session.pop(chat_key, None)
            return redirect(f"{reverse('learning_assistant')}?course={course.pk}#course-chat")
        if form.is_valid():
            conversation = history[-10:] + [{"role": "user", "content": form.cleaned_data["message"]}]
            try:
                reply = course_reply(course, user.role, conversation)
                if not isinstance(reply, str) or not reply.strip():
                    raise ChatError("The AI returned no reply. Please try again.", "empty_response")
            except ChatError as error:
                form.add_error(None, error.message)
                record_service("ai", False, "AI request failed: " + error.code + ".")
            except (OSError, ValueError):
                form.add_error(None, "Could not reach the AI service. Please try again shortly.")
                record_service("ai", False, "AI request failed: connection or response.")
            else:
                history = conversation + [{"role": "assistant", "content": reply}]
                request.session[chat_key] = history
                record_service("course_help" if chat_mode() == "free" else "ai", True, "Free course help returned lesson content." if chat_mode() == "free" else "AI provider returned a reply.")
                if request.headers.get("Accept") == "application/json":
                    return JsonResponse({"history": history})
                return redirect(f"{reverse('learning_assistant')}?course={course.pk}#course-chat")
        if request.method == "POST" and request.headers.get("Accept") == "application/json":
            errors = [str(error) for errors in form.errors.values() for error in errors]
            return JsonResponse({"error": " ".join(errors)}, status=400)
        context.update(chat_form=form, chat_history=history, chat_enabled=chat_mode() == "free" or bool(chat_configuration()[0]), chat_mode=chat_mode(), chat_lessons=course.lessons.filter(status="published")[:12])
    return render(request, "dashboard/assistant.html", context)






