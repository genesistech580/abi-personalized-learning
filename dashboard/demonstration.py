from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from accounts.models import User
from courses.models import Course
from recommendations.plans import topic_plan
from .models import PilotStudy

@login_required
def demonstration(request):
    if request.user.role not in {"administrator","lecturer"}: raise PermissionDenied
    course=Course.objects.filter(code="DSA200").first()
    if course and request.user.role=="lecturer" and course.lecturer_id!=request.user.pk: raise PermissionDenied
    plans=[]
    if course:
        for student in User.objects.filter(is_demo=True):
            attempt=student.diagnostic_attempts.filter(course=course,stage=request.GET.get("stage","diagnostic")).first()
            if attempt:
                plan=topic_plan(student,course,through=attempt.pk);plan["demo_name"]=student.username;plans.append(plan)
    return render(request,"dashboard/demonstration.html",{"learning_plans":plans,"demo_mode":True,"studies":PilotStudy.objects.all()})
