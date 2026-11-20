import csv
import io
import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from assessments.models import DiagnosticAttempt, DiagnosticQuestion, Assessment, Submission, PilotFeedback
from courses.models import Course, Enrollment, Lesson, LessonCompletion
from dashboard.models import AuditEvent, ResearchConsent, ConsentEvent


class AdministratorOperationsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("manager", role="administrator")
        self.teacher = User.objects.create_user("teacher", role="lecturer")
        self.student = User.objects.create_user("learner-private", email="private@example.com")
        self.course = Course.objects.create(code="ALG200", title="Algebra", lecturer=self.teacher)
        self.enrollment = Enrollment.objects.create(course=self.course, student=self.student)
        self.lesson = Lesson.objects.create(course=self.course, title="Introduction", content="Read this")
        self.client.force_login(self.admin)

    def attempt(self, stage="diagnostic", correct=0, key="approved-pair"):
        return DiagnosticAttempt.objects.create(course=self.course, student=self.student, stage=stage,
            comparison_key=key, results={"Variables": {"correct": correct, "total": 1}})

    def consent(self):
        return ResearchConsent.objects.create(student=self.student, consented_at=timezone.now()-timedelta(days=1), cohort="Group A")

    def test_admin_screens_render_and_other_roles_are_denied(self):
        for section in ["students", "lecturers", "courses", "enrollments", "content", "consent", "audit", "system"]:
            self.assertEqual(self.client.get(reverse("admin_hub", args=[section])).status_code, 200, section)
        for role in [self.student, self.teacher]:
            self.client.force_login(role)
            self.assertEqual(self.client.get(reverse("admin_hub", args=["audit"])).status_code, 403)
            self.assertEqual(self.client.get(reverse("admin_evaluation")+"?export=csv").status_code, 403)

    def test_archive_and_deactivate_preserve_academic_records(self):
        attempt = self.attempt()
        self.client.post(reverse("admin_course_state", args=[self.course.pk]))
        self.client.post(reverse("delete_account", args=[self.student.pk]))
        self.course.refresh_from_db(); self.student.refresh_from_db()
        self.assertIsNotNone(self.course.archived_at)
        self.assertFalse(self.student.is_active)
        self.assertTrue(DiagnosticAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())
        with self.assertRaises(ProtectedError), transaction.atomic():
            Course.objects.filter(pk=self.course.pk).delete()
        self.client.post(reverse("admin_course_state", args=[self.course.pk]))
        self.course.refresh_from_db(); self.assertIsNone(self.course.archived_at)

    def test_enrollment_correction_keeps_history_in_original_course(self):
        attempt = self.attempt()
        target = Course.objects.create(code="ICT201", title="ICT", lecturer=self.teacher)
        self.client.post(reverse("admin_enrollment", args=[self.enrollment.pk]), {"course": target.pk, "active": "on"})
        self.enrollment.refresh_from_db(); attempt.refresh_from_db()
        self.assertIsNotNone(self.enrollment.withdrawn_at)
        self.assertEqual(attempt.course_id, self.course.pk)
        self.assertTrue(Enrollment.objects.filter(course=target, student=self.student, withdrawn_at=None).exists())
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("diagnostic", args=[self.course.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("read_lesson", args=[self.lesson.pk])).status_code, 404)

    def test_admin_can_inspect_any_student_and_content(self):
        self.attempt()
        self.assertContains(self.client.get(reverse("admin_student", args=[self.student.pk])), "ALG200")
        self.assertContains(self.client.get(reverse("student_detail", args=[self.course.pk, self.student.pk])), "Variables")
        preview = self.client.get(reverse("content_preview", args=["lesson", self.lesson.pk]))
        self.assertContains(preview, "Read this")
        self.assertEqual(self.client.post(reverse("student_detail", args=[self.course.pk, self.student.pk]), {}).status_code, 403)

    def test_student_consent_is_voluntary_and_withdrawable(self):
        self.client.force_login(self.student)
        url = reverse("research_consent")
        self.client.post(url, {"action": "consent"})
        self.assertFalse(ResearchConsent.objects.filter(student=self.student).exists())
        self.client.post(url, {"action": "consent", "agree": "yes"})
        consent = ResearchConsent.objects.get(student=self.student)
        self.assertTrue(consent.active)
        self.client.post(url, {"action": "withdraw"})
        consent.refresh_from_db(); self.assertFalse(consent.active)
        self.assertTrue(self.student.is_active)
        self.assertEqual(ConsentEvent.objects.filter(student=self.student).count(), 2)

    def test_research_exports_filter_consent_group_and_pairs(self):
        consent = self.consent()
        self.attempt(); self.attempt("followup", 1)
        url = reverse("admin_evaluation")
        response = self.client.get(url, {"course": self.course.pk, "cohort": "Group A", "export": "csv"})
        rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows), 1)
        self.assertEqual(float(rows[0]["change"]), 100)
        self.assertNotIn(self.student.username, response.content.decode())
        self.assertNotIn(self.student.email, response.content.decode())
        self.assertContains(self.client.get(url, {"cohort": "Other"}), "No eligible records")
        consent.withdrawn_at = timezone.now(); consent.save()
        self.assertEqual(len(list(csv.DictReader(io.StringIO(self.client.get(url, {"export": "csv"}).content.decode())))), 0)

    def test_unapproved_pairs_and_records_before_consent_are_not_compared(self):
        self.attempt(); self.attempt("followup", 1)
        DiagnosticAttempt.objects.update(submitted_at=timezone.now()-timedelta(days=2))
        ResearchConsent.objects.create(student=self.student, consented_at=timezone.now())
        self.assertContains(self.client.get(reverse("admin_evaluation")), "0 comparable")
        self.attempt(key=""); self.attempt("followup", 1, key="")
        self.assertContains(self.client.get(reverse("admin_evaluation")), "0 comparable")

    def test_search_pagination_and_date_validation(self):
        for number in range(24):
            User.objects.create_user(f"test-person-{number}")
        response = self.client.get(reverse("admin_hub", args=["students"]), {"q": "test-person", "page": 2})
        self.assertEqual(response.context["page_obj"].paginator.count, 24)
        self.assertEqual(len(response.context["page_obj"]), 4)
        response = self.client.get(reverse("admin_evaluation"), {"start": "2026-12-01", "end": "2026-01-01", "export": "csv"})
        self.assertContains(response, "Start date must be before")
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_mutations_and_exports_have_audit_actor_without_sensitive_values(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("admin_course_state", args=[self.course.pk]))
        event = AuditEvent.objects.get(model_label="courses.course", object_id=str(self.course.pk))
        self.assertEqual(event.actor_id, self.admin.pk)
        self.assertIn("archived_at", event.fields)
        self.assertNotIn("Read this", json.dumps(event.fields))
        self.client.get(reverse("admin_evaluation"), {"export": "csv"})
        self.assertTrue(AuditEvent.objects.filter(action="export", actor=self.admin).exists())

    def test_feedback_is_available_beyond_java_and_requires_consent(self):
        self.attempt()
        self.client.force_login(self.student)
        data = {"course": self.course.pk, "ease": 4, "clarity": 4, "usefulness": 5}
        self.assertEqual(self.client.post(reverse("pilot_feedback"), data).status_code, 403)
        self.consent()
        self.assertEqual(self.client.post(reverse("pilot_feedback"), data).status_code, 302)
        self.assertTrue(PilotFeedback.objects.filter(student=self.student, course=self.course).exists())

    def test_grade_change_has_audit_entry_and_activity_notification(self):
        assessment = Assessment.objects.create(course=self.course, title="Assignment")
        submission = Submission.objects.create(assessment=assessment, student=self.student, answer="Private answer")
        self.client.force_login(self.teacher)
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("grade_submission", args=[submission.pk]), {
                    "score": 75, "feedback": "Private feedback", "submitted_version": submission.updated_at.isoformat()})
            self.assertEqual(response.status_code, 302)
            self.assertTrue((Path(folder) / ".activity-version").exists())
        event = AuditEvent.objects.get(model_label="assessments.submission", object_id=str(submission.pk))
        self.assertEqual(event.actor_id, self.teacher.pk)
        self.assertIn("score", event.fields)
        self.assertNotIn("Private", json.dumps(event.fields))

    def test_content_union_filters_and_paginates_questions(self):
        for number in range(24):
            DiagnosticQuestion.objects.create(course=self.course, topic="Variables", prompt=f"Question {number}",
                status="draft", option_a="One", option_b="Two", option_c="Three", correct="A")
        response = self.client.get(reverse("admin_hub", args=["content"]), {"course": self.course.pk, "status": "draft", "page": 2})
        self.assertEqual(response.context["page_obj"].paginator.count, 24)
        self.assertEqual(len(response.context["page_obj"]), 4)

    def test_research_model_predictions_do_not_use_later_peers(self):
        from dashboard.adminops import research_model_metrics
        self.consent()
        self.attempt()
        peer = User.objects.create_user("later-peer")
        ResearchConsent.objects.create(student=peer, consented_at=timezone.now()-timedelta(days=1))
        DiagnosticAttempt.objects.create(course=self.course, student=peer, stage="diagnostic",
            comparison_key="approved-pair", results={"Variables": {"correct": 1, "total": 1}})
        self.attempt("followup", 1)
        metrics = research_model_metrics({})
        self.assertEqual(metrics[0]["count"], 0)

    def test_email_monitor_records_failure_without_exposing_provider_details(self):
        from accounts.reset import MonitoredPasswordResetForm
        from dashboard.models import ServiceStatus
        form = MonitoredPasswordResetForm()
        context = {"user": self.student, "email": self.student.email, "domain": "example.com", "site_name": "ABI", "uid": "abc", "token": "test-token", "protocol": "https"}
        with patch("accounts.reset.EmailMultiAlternatives.send", side_effect=OSError("secret-provider-detail")):
            form.send_mail("registration/password_reset_subject.txt", "registration/password_reset_email.html", context, "sender@example.com", self.student.email)
        status = ServiceStatus.objects.get(service="email")
        self.assertFalse(status.successful)
        self.assertNotIn("secret-provider-detail", status.summary)
        with patch("accounts.reset.EmailMultiAlternatives.send", return_value=1):
            form.send_mail("registration/password_reset_subject.txt", "registration/password_reset_email.html", context, "sender@example.com", self.student.email)
        status.refresh_from_db(); self.assertTrue(status.successful)

    @override_settings(OPENAI_API_KEY="test-key")
    def test_ai_monitor_records_actual_success(self):
        from dashboard.models import ServiceStatus
        self.client.force_login(self.student)
        with patch("dashboard.assistant.course_reply", return_value="Review variables."):
            response = self.client.post(reverse("learning_assistant") + f"?course={self.course.pk}", {"message": "What is a variable?"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ServiceStatus.objects.get(service="ai").successful)

    def test_management_mutations_require_csrf_tokens(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(reverse("admin_course_state", args=[self.course.pk]))
        self.assertEqual(response.status_code, 403)
        self.course.refresh_from_db(); self.assertIsNone(self.course.archived_at)


class VerifiedBackupTests(TestCase):
    def test_backup_restores_database_and_media_in_isolation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); app = root / "app"; app.mkdir()
            media = app / "media"; media.mkdir(); (media / "portrait.jpg").write_bytes(b"sample-image")
            database = app / "live.sqlite3"
            with sqlite3.connect(database) as conn:
                conn.execute("CREATE TABLE sample (id integer primary key, value text)")
                conn.execute("INSERT INTO sample VALUES (1, 'retained')")
            conn.close()
            with override_settings(BASE_DIR=app, MEDIA_ROOT=media):
                with patch.dict(settings.DATABASES["default"], {"NAME": str(database)}):
                    call_command("backup_system", stdout=io.StringIO())
            status = json.loads((app / ".backup-status.json").read_text())
            self.assertTrue(status["last_attempt_ok"])
            self.assertEqual(status["media_files"], 1)
            self.assertEqual(len(list((root / "abi-scheduled-backups").glob("*/verified.json"))), 1)
            with sqlite3.connect(database) as conn:
                self.assertEqual(conn.execute("SELECT value FROM sample").fetchone()[0], "retained")
            conn.close()
