from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from accounts.profile import profile, profile_photo
from accounts.views import AccountLoginView, register
from assessments.diagnostics import add_diagnostic_question, diagnostic
from assessments.evaluation import pilot_evaluation
from assessments.feedback import pilot_feedback
from assessments.outcomes import outcomes
from assessments.views import grade, review, submit
from courses.views import add_lesson, enroll_course, learning_path, manage_course, read_lesson
from dashboard.assistant import learning_assistant
from dashboard.forms import AssessmentForm, CourseForm, EnrollmentForm, LecturerForm
from dashboard.views import create_record, index


urlpatterns = [
    path("assistant/", learning_assistant, name="learning_assistant"),
    path("pilot-evaluation/", pilot_evaluation, name="pilot_evaluation"),
    path("pilot-feedback/", pilot_feedback, name="pilot_feedback"),
    path("outcomes/", outcomes, name="outcomes"),
    path("courses/<int:pk>/diagnostic/", diagnostic, name="diagnostic"),
    path("courses/<int:pk>/diagnostic/questions/", add_diagnostic_question, name="add_diagnostic_question"),
    path("courses/<int:pk>/enroll/", enroll_course, name="enroll_course"),
    path("courses/<int:pk>/edit/", manage_course, name="edit_course"),
    path("courses/<int:pk>/delete/", manage_course, {"delete": True}, name="delete_course"),
    path("courses/<int:pk>/learn/", learning_path, name="learning_path"),
    path("courses/<int:pk>/lessons/add/", add_lesson, name="add_lesson"),
    path("lessons/<int:pk>/", read_lesson, name="read_lesson"),
    path("", index, name="dashboard"),
    path("accounts/profile/", profile, name="profile"),
    path("accounts/profile/photo/", profile_photo, name="profile_photo"),
    path("accounts/register/", register, name="register"),
    path("accounts/login/", AccountLoginView.as_view(), name="login"),
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password-reset/sent/", auth_views.PasswordResetDoneView.as_view(extra_context={"email_delivery_enabled": bool(settings.EMAIL_HOST)}), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/complete/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("lecturers/add/", create_record, {
        "form_class": LecturerForm, "title": "Add lecturer", "success_message": "Lecturer account created.",
    }, name="add_lecturer"),
    path("courses/add/", create_record, {
        "form_class": CourseForm, "title": "Add course", "success_message": "Course created.",
    }, name="add_course"),
    path("enrollments/add/", create_record, {
        "form_class": EnrollmentForm, "title": "Enroll student", "success_message": "Student enrolled.",
    }, name="add_enrollment"),
    path("assessments/add/", create_record, {
        "form_class": AssessmentForm, "title": "Add assessment", "success_message": "Assessment created.",
    }, name="add_assessment"),
    path("assessments/<int:pk>/submit/", submit, name="submit_assessment"),
    path("assessments/<int:pk>/review/", review, name="review_assessment"),
    path("submissions/<int:pk>/grade/", grade, name="grade_submission"),
    path("admin/", admin.site.urls),
]









