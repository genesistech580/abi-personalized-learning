from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models


class Assessment(models.Model):
    course = models.ForeignKey(
        "courses.Course", on_delete=models.CASCADE, related_name="assessments"
    )
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True)
    due_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self):
        return f"{self.course.code} - {self.title}"


class Submission(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessment_submissions"
    )
    answer = models.TextField()
    score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    feedback = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("assessment", "student"), name="unique_assessment_student"),
            models.CheckConstraint(condition=models.Q(score__lte=100), name="submission_score_at_most_100"),
        ]


class DiagnosticQuestion(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="diagnostic_questions")
    review_lesson = models.ForeignKey(
        "courses.Lesson", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="diagnostic_questions",
    )
    stage = models.CharField(max_length=12, choices=[("diagnostic", "Diagnostic"), ("followup", "Follow-up")], default="diagnostic")
    explanation = models.TextField(blank=True)
    practice = models.TextField(blank=True)
    topic = models.CharField(max_length=80)
    prompt = models.TextField()
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    correct = models.CharField(max_length=1, choices=[("A", "A"), ("B", "B"), ("C", "C")])

    class Meta:
        ordering = ("pk",)


class DiagnosticAttempt(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="diagnostic_attempts")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="diagnostic_attempts")
    results = models.JSONField()
    stage = models.CharField(max_length=12, default="diagnostic")
    comparison_key = models.CharField(max_length=64, blank=True)
    question_feedback = models.JSONField(default=list, blank=True)
    quiz_version = models.CharField(max_length=64, blank=True)
    review_opened = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    @property
    def correct_count(self):
        return sum(topic["correct"] for topic in self.results.values())

    @property
    def question_count(self):
        return sum(topic["total"] for topic in self.results.values())




class PilotFeedback(models.Model):
    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ease = models.PositiveSmallIntegerField()
    clarity = models.PositiveSmallIntegerField()
    usefulness = models.PositiveSmallIntegerField()
