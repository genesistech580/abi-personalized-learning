from django.conf import settings
from django.db import models
from django.utils import timezone


class Course(models.Model):
    archived_at = models.DateTimeField(null=True, blank=True)

    def delete(self, *args, **kwargs):
        self.archived_at = timezone.now()
        self.save(update_fields=["archived_at"])


    quiz_approval = models.CharField(max_length=64, blank=True)
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
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    def delete(self, *args, **kwargs):
        self.withdrawn_at = timezone.now()
        self.save(update_fields=["withdrawn_at"])


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
    status = models.CharField(max_length=10, default="published", choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")])
    content = models.TextField()

    class Meta:
        ordering = ("position", "pk")

    def __str__(self):
        return self.title


class LessonCompletion(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="completions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("lesson", "student"), name="unique_lesson_completion")
        ]



class LessonVisit(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    first_opened_at = models.DateTimeField(auto_now_add=True)
    last_opened_at = models.DateTimeField(auto_now=True)
    visits = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("lesson", "student"), name="unique_lesson_visit")
        ]



class LearningResource(models.Model):
    class Difficulty(models.TextChoices):
        FOUNDATION = "foundation", "Foundational"
        REVISION = "revision", "Revision"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Kind(models.TextChoices):
        NOTES = "notes", "Notes / PDF"
        VIDEO = "video", "Tutorial video"
        EXAMPLE = "example", "Worked example"
        PRACTICE = "practice", "Practice questions"
        CODE = "programming", "Programming exercise"
        REVISION = "revision", "Revision activity"

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="resources")
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=80)
    difficulty = models.CharField(max_length=12, choices=Difficulty.choices)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    content = models.TextField(blank=True)
    url = models.URLField(blank=True)
    attachment = models.FileField(upload_to="learning-resources/", blank=True)
    status = models.CharField(max_length=10, default="draft", choices=[("draft", "Draft"), ("published", "Published"), ("archived", "Archived")])

    class Meta:
        ordering = ("topic", "difficulty", "pk")

    def __str__(self):
        return self.title


class ResourceProgress(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    resource = models.ForeignKey(LearningResource, on_delete=models.PROTECT, related_name="progress_records")
    first_opened_at = models.DateTimeField(auto_now_add=True)
    last_opened_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("student", "resource"), name="unique_resource_progress")]
