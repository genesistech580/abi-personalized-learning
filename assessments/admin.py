from django.contrib import admin

from .models import Assessment


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

    list_display = ("title", "course", "due_at")
    list_filter = ("course",)
    search_fields = ("title", "course__code", "course__title")
    list_select_related = ("course",)
