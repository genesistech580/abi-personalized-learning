from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import User
from .profile import ProfileForm


class AccountEditForm(ProfileForm):
    class Meta(ProfileForm.Meta):
        fields = ("username", "first_name", "last_name", "email", "department", "is_active", "photo")


@login_required
@require_http_methods(["GET", "POST"])
def manage_account(request, pk, delete=False):
    if request.user.role != User.Role.ADMINISTRATOR:
        raise PermissionDenied
    account = get_object_or_404(
        User.objects.filter(role__in=(User.Role.STUDENT, User.Role.LECTURER), is_superuser=False),
        pk=pk,
    )
    if delete:
        if request.method == "POST":
            try:
                account.delete()
            except ProtectedError:
                messages.error(request, "Reassign this lecturer’s courses before deleting the account.")
            else:
                messages.success(request, "Account deactivated.")
                return redirect(reverse("dashboard") + "?section=people")
        return render(request, "accounts/delete.html", {"account": account})
    form = AccountEditForm(request.POST if request.method == "POST" else None, request.FILES, instance=account)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        if form.cleaned_data["remove_photo"] and "photo" not in request.FILES:
            user.photo = ""
        user.save()
        messages.success(request, "Account updated.")
        return redirect(reverse("dashboard") + "?section=people")
    return render(request, "dashboard/create.html", {"form": form, "title": "Edit " + account.get_role_display().lower()})

