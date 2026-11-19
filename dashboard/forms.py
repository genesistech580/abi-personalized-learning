from django.contrib.auth.forms import UserCreationForm
from django.forms import DateTimeInput, modelform_factory

from accounts.models import User
from assessments.models import Assessment
from courses.models import Course, Enrollment


class LecturerForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.LECTURER
        if commit:
            user.save()
        return user


CourseForm = modelform_factory(Course, fields=("code", "title", "lecturer"))
EnrollmentForm = modelform_factory(Enrollment, fields=("course", "student"))
AssessmentForm = modelform_factory(
    Assessment,
    fields=("course", "title", "instructions", "due_at"),
    labels={"due_at": "Due date and time (UTC)"},
    widgets={
        "due_at": DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        )
    },
)

