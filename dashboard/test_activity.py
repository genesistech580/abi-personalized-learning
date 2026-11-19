from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth.models import AnonymousUser
from accounts.models import User
from courses.models import LessonVisit
from dashboard.activity import record_activity
from dashboard.releases import activity_version, system_version


class ActivityRefreshTests(TestCase):
    def test_saved_changes_notify_only_after_commit(self):
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            with self.captureOnCommitCallbacks(execute=True):
                record_activity(User)
                self.assertEqual(activity_version(), "0")
            self.assertNotEqual(activity_version(), "0")

    def test_lesson_visits_do_not_trigger_refresh(self):
        with TemporaryDirectory() as folder, override_settings(BASE_DIR=Path(folder)):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                record_activity(LessonVisit)
            self.assertEqual(callbacks, [])
            self.assertEqual(activity_version(), "0")

    def test_activity_token_requires_login_and_is_not_cached(self):
        request = RequestFactory().get("/system/version/")
        request.user = AnonymousUser()
        response = system_version(request)
        self.assertNotIn(b'"activity"', response.content)
        self.assertIn("no-store", response["Cache-Control"])
        request.user = User(username="lecturer")
        self.assertIn(b'"activity"', system_version(request).content)
