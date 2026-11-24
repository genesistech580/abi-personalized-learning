from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.db import transaction
from accounts.models import User
from assessments.models import Assessment, Submission, DiagnosticAttempt, PilotFeedback, LearningFeedback
from courses.models import Course, Enrollment, Lesson, LearningResource, ResourceProgress, LessonCompletion
from courses.deletion import permanently_delete_course
from dashboard.models import AuditEvent


class CourseDeletionTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_user("delete-admin",role="administrator")
        self.teacher=User.objects.create_user("delete-teacher",role="lecturer")
        self.student=User.objects.create_user("delete-student")
        self.course=Course.objects.create(code="REMOVE",title="Temporary course",lecturer=self.teacher)
        self.kept=Course.objects.create(code="KEEP",title="Other course",lecturer=self.teacher)
        Enrollment.objects.create(course=self.course,student=self.student)
        lesson=Lesson.objects.create(course=self.course,title="Lesson",content="Content")
        LessonCompletion.objects.create(lesson=lesson,student=self.student)
        resource=LearningResource.objects.create(course=self.course,title="Resource",topic="Topic",difficulty="foundation",kind="notes")
        ResourceProgress.objects.create(resource=resource,student=self.student)
        assessment=Assessment.objects.create(course=self.course,title="Assignment")
        Submission.objects.create(assessment=assessment,student=self.student,answer="Answer")
        DiagnosticAttempt.objects.create(course=self.course,student=self.student,results={})
        PilotFeedback.objects.create(course=self.course,student=self.student,ease=4,clarity=4,usefulness=4)
        LearningFeedback.objects.create(course=self.course,student=self.student,lecturer=self.teacher,topic="Topic",comment="Comment",lesson=lesson)
        self.url=reverse("permanent_delete_course",args=[self.course.pk])
        self.client.force_login(self.admin)

    def test_confirmation_requires_exact_code_and_get_does_not_delete(self):
        self.assertContains(self.client.get(self.url),"Delete course permanently")
        self.client.post(self.url,{"confirmation":"WRONG"})
        self.assertTrue(Course.objects.filter(pk=self.course.pk).exists())

    def test_admin_can_delete_full_course_while_preserving_accounts_and_other_courses(self):
        self.assertEqual(self.client.post(self.url,{"confirmation":"REMOVE"}).status_code,302)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
        self.assertTrue(Course.objects.filter(pk=self.kept.pk).exists())
        self.assertEqual(User.objects.count(),3)
        for model in [Enrollment,Lesson,LessonCompletion,LearningResource,ResourceProgress,Assessment,Submission,DiagnosticAttempt,PilotFeedback,LearningFeedback]:
            self.assertEqual(model.objects.count(),0,model.__name__)
        self.assertTrue(AuditEvent.objects.filter(action="delete",object_id=str(self.course.pk)).exists())

    def test_other_roles_cannot_permanently_delete_and_bulk_guard_is_restored(self):
        for user in [self.teacher,self.student]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.url,{"confirmation":"REMOVE"}).status_code,403)
            with self.assertRaises(PermissionDenied): permanently_delete_course(self.course.pk,user)
        with self.assertRaises(ProtectedError),transaction.atomic(): Course.objects.filter(pk=self.kept.pk).delete()

    def test_delete_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(self.url,{"confirmation":"REMOVE"}).status_code,403)
