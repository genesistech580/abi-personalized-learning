from django.conf import settings
from django.db import models


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teaching_courses",
        limit_choices_to={"role": "lecturer"},
    )

    def __str__(self):
        return f"{self.code} - {self.title}"


class Enrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "student"},
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "student"], name="unique_course_student"),
        ]

    def __str__(self):
        return f"{self.student} in {self.course}"


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=1)
    content = models.TextField()

    class Meta:
        ordering = ("position", "pk")

    def __str__(self):
        return self.title


class LessonCompletion(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="completions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("lesson", "student"), name="unique_lesson_completion")
        ]
