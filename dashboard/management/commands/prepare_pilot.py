from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from courses.models import Course, Enrollment, LearningResource
from courses.study_pack import TOPICS, PACK, NOTES, VIDEOS
from assessments.models import DiagnosticAttempt
from assessments.publishing import signature, coverage
from dashboard.models import PilotStudy

class Command(BaseCommand):
    @transaction.atomic
    def handle(self,*args,**options):
        course=Course.objects.get(code="DSA200")
        first,second=coverage(course)
        if not first or first!=second: raise ValueError("Review mismatched quiz coverage first")
        for i,topic in enumerate(TOPICS):
            for level,kind,label,content in [
                ("foundation","notes","Study PDF",NOTES[i]),
                ("revision","example","Worked practice",PACK[i]["worked"]+"\n"+PACK[i]["practice"]+"\n"+PACK[i]["answers"]),
                ("intermediate","programming","Python lab",PACK[i]["code"]),
                ("advanced","programming","Extension project",PACK[i]["challenge"]),
                ("foundation","video","University lecture",PACK[i]["objectives"])]:
                item,_=LearningResource.objects.get_or_create(course=course,title=topic+" - "+label,topic=topic,difficulty=level,kind=kind,defaults={"content":content,"status":"published","url":VIDEOS[i] if kind=="video" else ""})
                if kind=="notes" and not item.attachment:
                    path=Path("courses/content/pdfs")/f"dsa-topic-{i+1}.pdf"
                    item.attachment.save(path.name,ContentFile(path.read_bytes()))
        study,created=PilotStudy.objects.get_or_create(group_code="UEW-DSA-PILOT",defaults={"course":course,"title":"UEW DSA pilot","active":True,"approval_recorded_at":timezone.now(),"approval_note":"Approval reported by project owner on 26 November 2026."})
        if created:
            course.quiz_approval=signature(course);course.save(update_fields=["quiz_approval"])
        for name,weak in [("demo-arrays",1),("demo-linked-lists",2),("demo-search-sort",4)]:
            user=User.objects.filter(username=name).first()
            if user and not user.is_demo: raise ValueError("Reserved demo name belongs to real account")
            if not user:
                user=User(username=name,is_demo=True,is_active=False);user.set_unusable_password();user.save()
            Enrollment.objects.get_or_create(student=user,course=course)
            if not user.diagnostic_attempts.filter(course=course).exists():
                for stage in ["diagnostic","followup"]:
                    results={topic:{"correct":(3 if i==weak else 8) if stage=="diagnostic" else (7 if i==weak else 9),"total":10} for i,topic in enumerate(TOPICS)}
                    DiagnosticAttempt.objects.create(student=user,course=course,stage=stage,comparison_key="demo:"+signature(course)[:59],results=results)
        self.stdout.write("Pilot materials and 3 isolated demos prepared; no real results created.")
