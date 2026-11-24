from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import User
from assessments.models import DiagnosticQuestion
from courses.models import Course, Lesson, LearningResource
from courses.dsa_curriculum import TOPICS, NOTES, EXAMPLES, EXERCISES, question_pairs


class Command(BaseCommand):
    help = "Create the DSA prototype without changing existing courses or student results."

    def add_arguments(self, parser):
        parser.add_argument("--lecturer")

    @transaction.atomic
    def handle(self, *args, **options):
        if Course.objects.filter(code="DSA200").exists():
            self.stdout.write("DSA200 already exists; existing teaching content preserved.")
            return
        teachers = User.objects.filter(role="lecturer", is_active=True).order_by("pk")
        teacher = teachers.filter(username=options["lecturer"]).first() if options["lecturer"] else teachers.first()
        if teacher is None:
            raise CommandError("Create an active lecturer before preparing DSA200.")
        course = Course.objects.create(code="DSA200", title="Data Structures and Algorithms", lecturer=teacher)
        for index, topic in enumerate(TOPICS):
            lesson = Lesson.objects.create(course=course, title=topic, position=index+1,
                content=NOTES[index] + "\n\n" + EXAMPLES[index] + "\n\nPractice\n" + EXERCISES[index], status="published")
            entries = [
                ("foundation", "notes", "Start here", NOTES[index]),
                ("foundation", "example", "Guided example", EXAMPLES[index]),
                ("foundation", "practice", "Remedial practice", "Write definitions for three terms in this topic. Trace the worked example by hand, explain each step and try a second example with different values.\n\n" + EXAMPLES[index]),
                ("revision", "practice", "Revision and practice", NOTES[index] + "\n\n" + EXERCISES[index]),
                ("intermediate", "programming", "Apply and implement", EXERCISES[index] + "\n\nState the input and expected output; implement a solution; test boundary cases and explain its running time."),
                ("advanced", "programming", "Extend and evaluate", EXERCISES[index] + "\n\nCompare two implementations, justify invariants, analyze worst-case time and memory, and design tests that expose incorrect assumptions."),
            ]
            for difficulty, kind, label, content in entries:
                LearningResource.objects.create(course=course, topic=topic, title=topic + " · " + label,
                    difficulty=difficulty, kind=kind, content=content, status="published")
            if index in {0,1}:
                LearningResource.objects.create(course=course, topic=topic, title=topic + " · MIT tutorial",
                    difficulty="foundation", kind="video", status="published", content="External MIT OpenCourseWare lecture on data structures and dynamic arrays.",
                    url="https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/resources/lecture-2-data-structures-and-dynamic-arrays/")
            for number, pair in enumerate(question_pairs(index)):
                for stage_index, stage in enumerate(["diagnostic", "followup"]):
                    prompt = pair[stage_index]
                    options = [value[stage_index] if isinstance(value, tuple) else value for value in pair[2:]]
                    correct_value = options[0]
                    rotation = (number + stage_index) % 3
                    options = options[rotation:] + options[:rotation]
                    DiagnosticQuestion.objects.create(course=course, review_lesson=lesson, topic=topic, stage=stage, status="published",
                        prompt=prompt, option_a=options[0], option_b=options[1], option_c=options[2], correct="ABC"[options.index(correct_value)],
                        explanation="The correct choice is: " + correct_value + ". Review the topic lesson for the underlying concept.", practice=EXERCISES[index])
        self.stdout.write(self.style.SUCCESS("DSA200 prepared: 5 lessons, 32 tagged resources, 50 diagnostic and 50 follow-up questions. Lecturer equivalence approval is still required."))
