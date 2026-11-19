from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render

from .models import User


class StudentRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = StudentRegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")

    return render(request, "registration/register.html", {"form": form})


class RememberMeForm(AuthenticationForm):
    remember_me = forms.BooleanField(required=False, label="Remember me")


class AccountLoginView(LoginView):
    authentication_form = RememberMeForm

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(14 * 24 * 60 * 60 if form.cleaned_data["remember_me"] else 0)
        return response

