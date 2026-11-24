import io
from tempfile import TemporaryDirectory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from assessments.models import DiagnosticAttempt, DiagnosticQuestion
from assessments.publishing import signature
from courses.models import Course, Enrollment, Lesson, LearningResource, ResourceProgress
from courses.resources import ResourceForm
from recommendations.plans import classify, topic_plan


class AdaptiveLearningTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("adaptive-teacher", role="lecturer")
        self.student = User.objects.create_user("adaptive-a")
        self.other = User.objects.create_user("adaptive-b")
        self.course = Course.objects.create(code="ADAPT", title="DSA", lecturer=self.teacher)
        for learner in [self.student, self.other]:
            Enrollment.objects.create(student=learner, course=self.course)
        for topic in ["Arrays", "Linked Lists"]:
            for difficulty in ["foundation", "revision", "intermediate", "advanced"]:
                LearningResource.objects.create(course=self.course, title=topic + " " + difficulty,
                    topic=topic, difficulty=difficulty, kind="practice", content="Practice this topic.", status="published")

    def attempt(self, student, results, stage="diagnostic", key="paired-version"):
        return DiagnosticAttempt.objects.create(student=student, course=self.course, results=results,
            stage=stage, comparison_key=key)

    def test_exact_performance_band_boundaries(self):
        for score, label in [(0,"Poor"),(39,"Poor"),(40,"Below average"),(49,"Below average"),(50,"Average"),(69,"Average"),(70,"Good"),(84,"Good"),(85,"Excellent"),(100,"Excellent")]:
            self.assertEqual(classify(score,100)["category"], label)
        self.assertIsNone(classify(0,0))

    def test_two_students_receive_different_topic_and_difficulty_resources(self):
        self.attempt(self.student, {"Arrays":{"correct":9,"total":10}, "Linked Lists":{"correct":4,"total":10}})
        self.attempt(self.other, {"Arrays":{"correct":4,"total":10}, "Linked Lists":{"correct":9,"total":10}})
        first = topic_plan(self.student,self.course)["topics"]
        second = topic_plan(self.other,self.course)["topics"]
        self.assertEqual(first[0]["name"],"Linked Lists")
        self.assertEqual(second[0]["name"],"Arrays")
        self.assertEqual(first[0]["resources"][0]["item"].difficulty,"foundation")
        self.assertEqual(first[-1]["resources"][0]["item"].difficulty,"advanced")

    def test_followup_40_to_75_moves_from_foundation_to_intermediate(self):
        self.attempt(self.student,{"Linked Lists":{"correct":8,"total":20}})
        self.attempt(self.student,{"Linked Lists":{"correct":15,"total":20}},"followup")
        topic=topic_plan(self.student,self.course)["topics"][0]
        self.assertEqual(topic["change"],35)
        self.assertEqual(topic["category"],"Good")
        self.assertEqual(topic["resources"][0]["item"].difficulty,"intermediate")

    def test_unmatched_versions_do_not_claim_improvement(self):
        self.attempt(self.student,{"Arrays":{"correct":4,"total":10}},key="old")
        self.attempt(self.student,{"Arrays":{"correct":9,"total":10}},"followup",key="new")
        self.assertIsNone(topic_plan(self.student,self.course)["topics"][0]["change"])

    def test_resource_access_completion_and_draft_boundaries(self):
        resource=self.course.resources.first()
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("resource_detail",args=[resource.pk])).status_code,200)
        self.client.post(reverse("resource_detail",args=[resource.pk]))
        self.assertIsNotNone(ResourceProgress.objects.get(student=self.student,resource=resource).completed_at)
        resource.status="draft"; resource.save()
        self.assertEqual(self.client.get(reverse("resource_detail",args=[resource.pk])).status_code,404)
        self.assertEqual(self.client.get(reverse("edit_resource",args=[self.course.pk,resource.pk])).status_code,403)
        stranger=User.objects.create_user("unassigned-student")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("course_resources",args=[self.course.pk])).status_code,404)

    def test_pdf_validation_and_external_link_validation(self):
        data={"title":"Notes","topic":"Arrays","difficulty":"foundation","kind":"notes","status":"draft"}
        invalid=ResourceForm(data,{"attachment":SimpleUploadedFile("attack.pdf",b"<script>bad</script>")})
        self.assertFalse(invalid.is_valid())
        invalid=ResourceForm({**data,"url":"http://example.com/notes"})
        self.assertFalse(invalid.is_valid())
        valid=ResourceForm(data,{"attachment":SimpleUploadedFile("notes.pdf",b"%PDF-1.4 test")})
        self.assertTrue(valid.is_valid(), valid.errors)

    def test_learning_plan_and_performance_render_for_student(self):
        self.attempt(self.student,{"Arrays":{"correct":4,"total":10}})
        self.client.force_login(self.student)
        self.assertContains(self.client.get('/?section=recommended'),"Below average")
        self.assertContains(self.client.get('/?section=performance'),"40%")

    def test_dsa_preparation_is_idempotent_and_requires_lecturer_approval(self):
        output=io.StringIO()
        call_command("prepare_dsa",lecturer=self.teacher.username,stdout=output)
        course=Course.objects.get(code="DSA200")
        self.assertEqual(course.lessons.count(),5)
        self.assertEqual(course.resources.count(),32)
        for stage in ["diagnostic","followup"]:
            self.assertEqual(course.diagnostic_questions.filter(stage=stage).count(),50)
        self.assertFalse(course.quiz_approval)
        course.title="Lecturer's edited title"; course.save()
        call_command("prepare_dsa",stdout=io.StringIO())
        course.refresh_from_db(); self.assertEqual(course.title,"Lecturer's edited title")
        self.assertEqual(course.resources.count(),32)

    def test_full_dsa_diagnostic_then_approved_followup_updates_the_plan(self):
        import re
        call_command("prepare_dsa", lecturer=self.teacher.username, stdout=io.StringIO())
        course=Course.objects.get(code="DSA200")
        Enrollment.objects.create(student=self.student,course=course)
        self.client.force_login(self.student)
        path=reverse("diagnostic",args=[course.pk])
        page=self.client.get(path)
        version=re.search(rb'name="quiz_version" value="([^"]+)"',page.content)[1].decode()
        questions=list(course.diagnostic_questions.filter(stage="diagnostic"))
        answers={str(question.pk):question.correct for question in questions}
        self.assertEqual(self.client.post(path,{"quiz_version":version,**answers}).status_code,302)
        baseline=course.diagnostic_attempts.get(student=self.student)
        self.assertEqual(baseline.question_count,50)
        self.assertTrue(baseline.comparison_key)
        # Review approves this unchanged pair, including the previously recorded baseline.
        course.quiz_approval=signature(course);course.save(update_fields=["quiz_approval"])
        page=self.client.get(path+"?stage=followup")
        version=re.search(rb'name="quiz_version" value="([^"]+)"',page.content)[1].decode()
        answers={str(question.pk):question.correct for question in course.diagnostic_questions.filter(stage="followup")}
        self.client.post(path+"?stage=followup",{"quiz_version":version,**answers})
        plan=topic_plan(self.student,course)
        self.assertTrue(all(topic["change"]==0 for topic in plan["topics"]))
        self.assertTrue(all(topic["category"]=="Excellent" for topic in plan["topics"]))
        self.assertTrue(all(topic["resources"][0]["item"].difficulty=="advanced" for topic in plan["topics"]))

    def test_followup_requires_a_diagnostic_first(self):
        DiagnosticQuestion.objects.create(course=self.course,stage="diagnostic",topic="Arrays",prompt="Diagnostic",option_a="A",option_b="B",option_c="C",correct="A")
        DiagnosticQuestion.objects.create(course=self.course,stage="followup",topic="Arrays",prompt="Follow-up",option_a="A",option_b="B",option_c="C",correct="A")
        self.course.quiz_approval=signature(self.course);self.course.save()
        self.client.force_login(self.student)
        response=self.client.get(reverse("diagnostic",args=[self.course.pk])+"?stage=followup")
        self.assertEqual(response.status_code,302)
        self.assertFalse(self.student.diagnostic_attempts.exists())

    def test_readiness_reports_pending_approval_without_changing_course(self):
        from courses.readiness import dsa_readiness
        call_command("prepare_dsa", lecturer=self.teacher.username, stdout=io.StringIO())
        result = dsa_readiness()
        self.assertEqual(result["topics"], 5)
        self.assertEqual(result["diagnostic_questions"], 50)
        self.assertEqual(result["followup_questions"], 50)
        self.assertTrue(result["matched_coverage"])
        self.assertFalse(result["approved"])
        self.assertEqual(result["missing_resources"], [])
        self.assertEqual(Course.objects.get(code="DSA200").quiz_approval, "")
