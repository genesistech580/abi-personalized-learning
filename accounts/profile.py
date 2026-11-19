from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from .models import User


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "photo")
        labels = {"photo": "Profile photo"}
        widgets = {"photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png"})}

    remove_photo = forms.BooleanField(required=False, label="Remove photo")

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if "photo" not in self.files:
            return photo
        if photo.size > 5 * 1024 * 1024:
            raise ValidationError("Choose a photo under 5 MB.")
        signature = photo.read(8)
        photo.seek(0)
        if signature.startswith(bytes.fromhex("ffd8ff")):
            extension = "jpg"
        elif signature == bytes.fromhex("89504e470d0a1a0a"):
            extension = "png"
        else:
            raise ValidationError("Choose a JPEG or PNG photo.")
        photo.name = f"{uuid4().hex}.{extension}"
        return photo


@login_required
def profile(request):
    user = request.user
    previous_photo = user.photo.name
    form = ProfileForm(request.POST if request.method == "POST" else None, request.FILES, instance=user)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        if form.cleaned_data["remove_photo"] and "photo" not in request.FILES:
            user.photo = ""
        user.save(update_fields=list(form.Meta.fields))
        if previous_photo and previous_photo != user.photo.name:
            storage = user.photo.storage
            transaction.on_commit(lambda: storage.delete(previous_photo))
        messages.success(request, "Profile saved.")
        return redirect("profile")
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def profile_photo(request):
    photo = request.user.photo
    if not photo:
        raise Http404
    try:
        stream = photo.open("rb")
    except FileNotFoundError as error:
        raise Http404 from error
    content_type = "image/png" if photo.name.endswith(".png") else "image/jpeg"
    response = FileResponse(stream, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
