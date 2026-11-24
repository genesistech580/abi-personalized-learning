from uuid import uuid4
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from .models import Course, LearningResource, ResourceProgress


def available_courses(user):
    if user.role == "administrator":
        return Course.objects.all()
    if user.role == "lecturer":
        return user.teaching_courses.all()
    return Course.objects.filter(enrollments__student=user, enrollments__withdrawn_at__isnull=True, archived_at__isnull=True)


class ResourceForm(forms.ModelForm):
    class Meta:
        model = LearningResource
        fields = ("title", "topic", "difficulty", "kind", "content", "url", "attachment", "status")
        labels = {"topic": "Topic (match a quiz topic)"}
        widgets = {"topic": forms.TextInput(attrs={"list": "resource-topics"}), "attachment": forms.FileInput(attrs={"accept": "application/pdf"})}

    def clean_topic(self):
        return " ".join(self.cleaned_data["topic"].split())

    def clean_url(self):
        url = self.cleaned_data["url"]
        if url and not url.startswith("https://"):
            raise forms.ValidationError("Use a secure HTTPS resource link.")
        return url

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if "attachment" not in self.files:
            return attachment
        if attachment.size > 10 * 1024 * 1024 or not attachment.read(5).startswith(b"%PDF-"):
            raise forms.ValidationError("Choose a PDF under 10 MB.")
        attachment.seek(0)
        return ContentFile(attachment.read(), name=uuid4().hex + ".pdf")

    def clean(self):
        data = super().clean()
        if not any(data.get(field) for field in ("content", "url", "attachment")):
            raise forms.ValidationError("Add content, a resource link or a PDF.")
        return data


@login_required
@require_http_methods(["GET", "POST"])
def resources(request, pk, resource_id=None):
    course = get_object_or_404(available_courses(request.user), pk=pk)
    can_edit = request.user.role in {"administrator", "lecturer"}
    if resource_id is not None or request.GET.get("add") == "1":
        if not can_edit:
            raise PermissionDenied
        item = get_object_or_404(course.resources, pk=resource_id) if resource_id else None
        form = ResourceForm(request.POST if request.method == "POST" else None, request.FILES, instance=item)
        if request.method == "POST" and form.is_valid():
            saved = form.save(commit=False)
            saved.course = course
            saved.save()
            messages.success(request, "Resource saved.")
            return redirect("course_resources", pk=course.pk)
        return render(request, "courses/resource_form.html", {"form": form, "course": course, "topics": sorted(set(course.diagnostic_questions.values_list("topic", flat=True)))})
    if request.method != "GET":
        raise PermissionDenied
    items = course.resources.all() if can_edit else course.resources.filter(status="published")
    return render(request, "courses/resources.html", {"course": course, "items": items, "can_edit": can_edit})


@login_required
@require_http_methods(["GET", "POST"])
def resource_detail(request, pk, download=False):
    items = LearningResource.objects.filter(course__in=available_courses(request.user)).select_related("course")
    if request.user.role == "student":
        items = items.filter(status="published")
    item = get_object_or_404(items, pk=pk)
    progress = None
    if request.user.role == "student":
        progress, created = ResourceProgress.objects.get_or_create(student=request.user, resource=item)
        if not created and request.method == "GET":
            ResourceProgress.objects.filter(pk=progress.pk).update(last_opened_at=timezone.now())
        if request.method == "POST":
            progress.completed_at = timezone.now()
            progress.save(update_fields=["completed_at", "last_opened_at"])
            messages.success(request, "Resource marked complete. Your latest quiz determines the next recommendation.")
            return redirect(reverse("dashboard") + "?section=recommended")
    elif request.method == "POST":
        raise PermissionDenied
    if download:
        if not item.attachment:
            raise Http404
        try:
            response = FileResponse(item.attachment.open("rb"), as_attachment=True, filename="learning-resource.pdf", content_type="application/pdf")
        except FileNotFoundError:
            raise Http404
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    return render(request, "courses/resource.html", {"item": item, "progress": progress})
