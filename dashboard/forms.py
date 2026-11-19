from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from accounts.profile import ProfileForm
from django.forms import DateTimeInput, modelform_factory

from accounts.models import User
from assessments.models import Assessment
from courses.models import Course, Enrollment


class LecturerForm(ProfileForm):
    email = forms.EmailField(label="Gmail")
    department = forms.CharField(max_length=120)
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta(ProfileForm.Meta):
        fields = ("username", "email", "department", "photo")
        labels = {"photo": "Passport picture (optional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("remove_photo")
        self.order_fields(("username", "email", "department", "password", "photo"))
        for field in self.fields.values():
            field.help_text = ""

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            user = User(
                username=cleaned.get("username", ""),
                email=cleaned.get("email", ""),
            )
            try:
                validate_password(password, user)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.LECTURER
        user.set_password(self.cleaned_data["password"])
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


