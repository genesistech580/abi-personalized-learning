from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class LearningUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = self.model.Role.ADMINISTRATOR
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save(update_fields=["is_active"])


    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        LECTURER = "lecturer", "Lecturer"
        ADMINISTRATOR = "administrator", "Administrator"

    role = models.CharField(max_length=13, choices=Role.choices, default=Role.STUDENT)
    department = models.CharField(max_length=120, blank=True)
    photo = models.FileField(upload_to="profiles/", blank=True)
    objects = LearningUserManager()

