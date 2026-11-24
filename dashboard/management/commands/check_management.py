"""Render administrator read-only screens against the deployed database."""
from django.core.management.base import BaseCommand, CommandError
from django.test import RequestFactory
from accounts.models import User
from courses.models import Enrollment, Lesson
from dashboard import adminops
from dashboard.views import index
from dashboard.teaching import teaching, content_preview


class Command(BaseCommand):
    help = "Read-only smoke check of administrator screens; no login or data changes."

    def handle(self, *args, **options):
        admin = User.objects.filter(role="administrator", is_active=True).first()
        if admin is None:
            self.stdout.write("No active administrator; management smoke check skipped.")
            return
        factory = RequestFactory()
        count = 0

        def check(view, path, **kwargs):
            nonlocal count
            request = factory.get(path)
            request.user = admin
            request.session = {}
            response = view(request, **kwargs)
            if response.status_code != 200:
                raise CommandError("Administrator read-only screen did not respond successfully.")
            count += 1

        for section in ["students", "lecturers", "courses", "enrollments", "content", "consent", "audit", "system"]:
            check(adminops.hub, "/management/" + section + "/", section=section)
        check(adminops.evaluation, "/evaluation/")
        enrollment = Enrollment.objects.select_related("student").filter(student__role="student").first()
        if enrollment:
            check(adminops.student, "/management/student/", pk=enrollment.student_id)
            check(teaching, "/teaching/student/", pk=enrollment.course_id, student_id=enrollment.student_id)
        lesson = Lesson.objects.first()
        if lesson:
            check(content_preview, "/teaching/preview/", kind="lesson", pk=lesson.pk)
        learner = User.objects.filter(role="student", is_active=True).first()
        if learner:
            for section in ["overview", "recommended", "performance"]:
                request = factory.get("/", {"section": section})
                request.user = learner
                request.session = {}
                if index(request).status_code != 200:
                    raise CommandError("Student learning profile did not render.")
                count += 1
        self.stdout.write(self.style.SUCCESS(f"{count} administrator/student read-only screens rendered successfully."))
