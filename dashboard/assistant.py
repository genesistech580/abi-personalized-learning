import json
from urllib.error import HTTPError

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, OuterRef, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from assessments.models import DiagnosticAttempt, Submission
from courses.models import Course, LessonCompletion
from recommendations.services import diagnostic_reviews


from .services import record_service
from .chat import course_reply


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
                if result["correct"] < result["total"]:
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
        form = ChatForm(request.POST if request.method == "POST" else None)
        if form.is_valid():
            if not settings.OPENAI_API_KEY:
                form.add_error(None, "AI chat is not configured yet.")
            else:
                messages = history[-6:] + [{"role": "user", "content": form.cleaned_data["message"]}]
                try:
                    reply = course_reply(course, user.role, messages)
                except HTTPError as error:
                    errors = {
                        401: "OpenAI rejected the API key.",
                        403: "The API key lacks permission for this request.",
                        404: "The AI model is unavailable to this API project.",
                        429: "OpenAI usage limit reached. Check API billing and quota.",
                    }
                    if error.code == 429:
                        try:
                            provider_code = json.load(error).get("error", {}).get("code")
                        except (ValueError, AttributeError, OSError):
                            provider_code = None
                        if provider_code == "insufficient_quota":
                            errors[429] = "OpenAI API quota is unavailable. Ask the administrator to check API billing."
                        elif provider_code == "rate_limit_exceeded":
                            errors[429] = "Too many AI requests. Wait a moment and try again."
                    form.add_error(None, errors.get(error.code, f"OpenAI returned HTTP {error.code}."))
                    reply = ""
                except OSError:
                    form.add_error(None, "The server could not reach OpenAI.")
                    reply = ""
                except ValueError:
                    reply = ""
                record_service("ai", bool(reply), "AI provider returned a reply." if reply else "AI request failed; check provider access, quota or connectivity.")
                if reply:
                    request.session[chat_key] = messages + [{"role": "assistant", "content": reply}]
                    return redirect(f"{reverse('learning_assistant')}?course={course.pk}#course-chat")
                if not form.errors:
                    form.add_error(None, "OpenAI returned no reply. Please try again.")
        context.update(chat_form=form, chat_history=history, chat_enabled=bool(settings.OPENAI_API_KEY))
    return render(request, "dashboard/assistant.html", context)






