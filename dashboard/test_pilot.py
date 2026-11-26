from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from courses.models import Course, Enrollment
from assessments.models import DiagnosticAttempt
from dashboard.models import ResearchConsent
from dashboard.adminops import research_rows, research_model_metrics
from recommendations.plans import topic_plan

class PilotIsolationTests(TestCase):
    def test_synthetic_results_never_enter_research_even_with_consent(self):
        teacher=User.objects.create_user("pilot-teacher",role="lecturer")
        student=User.objects.create_user("synthetic",is_demo=True)
        course=Course.objects.create(code="PILOTTEST",title="Test",lecturer=teacher)
        Enrollment.objects.create(student=student,course=course)
        ResearchConsent.objects.create(student=student,consented_at=timezone.now())
        DiagnosticAttempt.objects.create(student=student,course=course,results={"Arrays":{"correct":3,"total":10}})
        self.assertEqual(research_rows({}),[])
        self.assertEqual(research_model_metrics({}),[])
