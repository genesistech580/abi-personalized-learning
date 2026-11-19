import re

from django.test import TestCase

from accounts.models import User
from assessments.models import DiagnosticAttempt, DiagnosticQuestion
from courses.models import Course, Enrollment, Lesson, LessonCompletion, LessonVisit
from recommendations.learner_model import evaluate


class LearningWorkflowTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", role="lecturer")
        self.student = User.objects.create_user("student")
        self.course = Course.objects.create(code="TEST", title="Programming", lecturer=self.teacher)
        self.lesson = Lesson.objects.create(course=self.course, title="Variables", content="Study variables.")
        for stage in ("diagnostic", "followup"):
            DiagnosticQuestion.objects.create(
                course=self.course, stage=stage, topic="Variables", prompt=f"Question {stage}",
                option_a="One", option_b="Two", option_c="Three", correct="A",
                explanation="Use a type before the variable name.", practice="Declare a count.",
                review_lesson=self.lesson,
            )
        self.client.force_login(self.student)

        from assessments.publishing import signature
        self.course.quiz_approval = signature(self.course)
        self.course.save(update_fields=["quiz_approval"])

    def answer(self, stage, answer):
        url = f"/courses/{self.course.pk}/diagnostic/?stage={stage}"
        page = self.client.get(url)
        version = re.search(rb'name="quiz_version" value="([^"]+)"', page.content)[1].decode()
        question = self.course.diagnostic_questions.get(stage=stage)
        return self.client.post(url, {"quiz_version": version, str(question.pk): answer})

    def test_diagnostic_feedback_and_followup(self):
        response = self.client.post(f"/courses/{self.course.pk}/enroll/")
        self.assertEqual(response.url, f"/courses/{self.course.pk}/diagnostic/")
        self.assertEqual(self.answer("diagnostic", "B").status_code, 302)
        attempt = DiagnosticAttempt.objects.get(student=self.student)
        self.assertIn("Use a type", attempt.question_feedback[0]["explanation"])
        self.assertEqual(self.answer("followup", "A").status_code, 302)
        self.assertEqual(self.student.diagnostic_attempts.count(), 2)
        keys = list(self.student.diagnostic_attempts.values_list("comparison_key", flat=True))
        self.assertEqual(keys[0], keys[1])
        self.assertContains(self.client.get("/outcomes/"), "100.0%")
        self.assertFalse(evaluate(self.course.pk)["enabled"])

    def test_activity_and_access(self):
        url = f"/lessons/{self.lesson.pk}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(LessonVisit.objects.get(student=self.student).visits, 2)
        self.client.post(url)
        self.assertIsNotNone(LessonCompletion.objects.get(student=self.student).completed_at)

    def test_stale_quiz_rejected(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        question = self.course.diagnostic_questions.get(stage="diagnostic")
        response = self.client.post(
            f"/courses/{self.course.pk}/diagnostic/",
            {"quiz_version": "old", str(question.pk): "A"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.student.diagnostic_attempts.exists())


class LecturerManagementTests(LearningWorkflowTests):
    def test_roster_feedback_and_permissions(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        url = f"/teaching/courses/{self.course.pk}/students/{self.student.pk}/"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(url), self.student.username)
        self.assertEqual(self.client.post(url, {
            "topic": "Variables", "comment": "Review declarations.", "lesson": self.lesson.pk,
        }).status_code, 302)
        self.client.force_login(self.student)
        self.assertContains(self.client.get("/?section=recommended"), "Review declarations.")
        other = User.objects.create_user("other-teacher", role="lecturer")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_edit_archive_and_approval_invalidation(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.force_login(self.teacher)
        url = f"/teaching/lesson/{self.lesson.pk}/edit/"
        self.assertEqual(self.client.post(url, {
            "title": self.lesson.title, "position": 1, "content": "Updated", "status": "archived",
        }).status_code, 302)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(f"/lessons/{self.lesson.pk}/").status_code, 404)
        from assessments.publishing import approved
        self.course.refresh_from_db()
        self.assertTrue(approved(self.course))
        question = self.course.diagnostic_questions.first()
        question.prompt = "Changed question"
        question.save()
        self.assertFalse(approved(self.course))
        self.assertEqual(self.client.get(f"/courses/{self.course.pk}/diagnostic/?stage=followup").status_code, 302)
        self.assertFalse(self.student.diagnostic_attempts.exists())

    def test_snapshot_survives_question_change(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.answer("diagnostic", "B")
        attempt = self.student.diagnostic_attempts.get()
        original = attempt.question_snapshot[0]["prompt"]
        question = self.course.diagnostic_questions.get(stage="diagnostic")
        question.prompt = "Revised"
        question.save()
        attempt.refresh_from_db()
        self.assertEqual(attempt.question_snapshot[0]["prompt"], original)

