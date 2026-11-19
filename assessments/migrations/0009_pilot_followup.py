from django.db import migrations


def add_followup(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    Question = apps.get_model("assessments", "DiagnosticQuestion")
    Lesson = apps.get_model("courses", "Lesson")
    course = Course.objects.filter(code="PILOT-JAVA").first()
    if not course:
        return
    rows = [
        ("Variables", "Which declaration stores a whole-number count?", "int count = 6;", "count = int 6;", "boolean count = 6;", "A", "Declare a variable using its type, name, and initial value.", "Declare a whole-number variable named seats."),
        ("Variables", "After int attempts = 2;, how do you set its value to 4?", "4 = attempts;", "attempts = 4;", "int = attempts;", "B", "Assign a new value using the existing variable name.", "Set seats to a different value."),
        ("Numeric types", "Which type stores a price of 8.75?", "boolean", "int", "double", "C", "double stores fractional numeric values.", "Declare a variable for a temperature of 24.5."),
        ("Numeric types", "Which declaration stores a whole-number age?", "int age = 20;", "boolean age = 20;", "int age = 20.5;", "A", "int stores whole numbers.", "Declare a count of books."),
        ("Booleans and strings", "Which declaration stores a true/false state?", "String ready = false;", "boolean ready = false;", "int ready = false;", "B", "boolean stores true or false without quotation marks.", "Declare a boolean named finished."),
        ("Booleans and strings", "Which declaration stores the course name?", "int course = 10;", "boolean course = true;", 'String course = "Java";', "C", "String stores text enclosed in double quotes.", "Declare a String for a city name."),
    ]
    for topic, prompt, a, b, c, answer, explanation, practice in rows:
        lesson = Lesson.objects.filter(course=course, title=topic).first()
        Question.objects.get_or_create(
            course=course, stage="followup", prompt=prompt,
            defaults=dict(topic=topic, option_a=a, option_b=b, option_c=c, correct=answer,
                          explanation=explanation, practice=practice, review_lesson=lesson),
        )
    for question in Question.objects.filter(course=course, stage="diagnostic"):
        matching = next((row for row in rows if row[0] == question.topic), None)
        if matching and not question.explanation:
            question.explanation = matching[6]
            question.practice = matching[7]
            question.save(update_fields=["explanation", "practice"])


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0008_diagnosticattempt_comparison_key_and_more"),
        ("courses", "0003_lessoncompletion_completed_at_lessonvisit"),
    ]
    operations = [migrations.RunPython(add_followup, migrations.RunPython.noop)]
