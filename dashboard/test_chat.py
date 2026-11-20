import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.models import User
from courses.models import Course, Enrollment
from dashboard.chat import ChatError, chat_configuration, request_reply, response_text
from dashboard.models import AuditEvent


class ChatTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("chat-admin", role="administrator")
        self.teacher = User.objects.create_user("chat-teacher", role="lecturer")
        self.student = User.objects.create_user("chat-student")
        self.course = Course.objects.create(code="CHAT200", title="Algebra", lecturer=self.teacher)
        Enrollment.objects.create(course=self.course, student=self.student)
        self.url = reverse("learning_assistant") + f"?course={self.course.pk}"

    def test_admin_can_configure_privately_without_echoing_or_logging_key(self):
        self.client.force_login(self.admin)
        key = "sk-test-private-never-display"
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            response = self.client.post(reverse("admin_hub", args=["system"]), {"action": "configure_ai", "key": key, "model": "gpt-4.1-mini"})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(chat_configuration()[0], key)
            page = self.client.get(reverse("admin_hub", args=["system"]))
            self.assertNotContains(page, key)
            self.assertNotIn(key, json.dumps(list(AuditEvent.objects.values("fields"))))

    def test_other_roles_cannot_configure_or_probe_keys(self):
        for user in [self.student, self.teacher]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(reverse("admin_hub", args=["system"]), {"action": "test_ai"}).status_code, 403)

    def test_response_parsing_handles_reasoning_refusal_and_malformed_output(self):
        response = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": "A variable is a symbol."}]}]}
        self.assertEqual(response_text(response), "A variable is a symbol.")
        self.assertEqual(response_text({"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "I can offer a hint."}]}]}), "I can offer a hint.")
        for invalid in [None, {"output": None}, {"output": [{"type": "message", "content": None}]}]:
            with self.assertRaises(ChatError): response_text(invalid)

    @override_settings(OPENAI_API_KEY="sk-unit-test")
    def test_quota_is_reported_as_billing_not_a_retry_loop(self):
        error = HTTPError("https://api.openai.com/v1/responses", 429, "quota", {}, io.BytesIO(json.dumps({"error": {"code": "credit_balance_exhausted", "message": "private-provider-detail"}}).encode()))
        with patch("dashboard.chat.urlopen", side_effect=error) as provider:
            with self.assertRaises(ChatError) as caught:
                request_reply([{"role": "user", "content": "Hello"}], "Help.")
        self.assertEqual(caught.exception.code, "quota")
        self.assertNotIn("private-provider-detail", caught.exception.message)
        self.assertEqual(provider.call_count, 1)

    def test_student_and_lecturer_get_ajax_replies_with_bounded_history(self):
        for user in [self.student, self.teacher]:
            self.client.force_login(user)
            with patch("dashboard.assistant.course_reply", return_value="A variable represents a value."):
                response = self.client.post(self.url, {"message": "What is a variable?"}, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["history"][-1]["content"], "A variable represents a value.")
            self.assertLessEqual(len(response.json()["history"]), 12)

    def test_failure_preserves_question_and_does_not_append_fake_reply(self):
        self.client.force_login(self.student)
        with patch("dashboard.assistant.course_reply", side_effect=ChatError("Check API billing.", "quota")):
            response = self.client.post(self.url, {"message": "Explain algebra"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Check API billing.")
        self.assertNotIn(f"course-chat:{self.course.pk}", self.client.session)

    def test_archived_and_unenrolled_courses_cannot_be_chatted_with(self):
        self.client.force_login(self.student)
        other = Course.objects.create(code="PRIVATE", title="Other", lecturer=self.teacher)
        self.assertEqual(self.client.post(reverse("learning_assistant") + f"?course={other.pk}", {"message": "Hello"}).status_code, 404)

    @override_settings(OPENAI_API_KEY="")
    def test_missing_key_is_explained_without_inventing_a_reply(self):
        self.client.force_login(self.student)
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            self.assertContains(self.client.get(self.url), "Chat is not enabled yet")
            response = self.client.post(self.url, {"message": "Hello"}, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("System status", response.json()["error"])
