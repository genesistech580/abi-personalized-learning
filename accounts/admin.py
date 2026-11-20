from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class LearningUserAdmin(UserAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

    fieldsets = (*UserAdmin.fieldsets, ("Learning system", {"fields": ("role",)}))
    add_fieldsets = (
        *UserAdmin.add_fieldsets,
        ("Learning system", {"fields": ("role",)}),
    )
    list_display = (*UserAdmin.list_display, "role")
    list_filter = (*UserAdmin.list_filter, "role")
