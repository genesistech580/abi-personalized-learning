from pathlib import Path
import sys
import textwrap
from xml.sax.saxutils import escape
sys.path.insert(0, str(Path.cwd()))
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from courses.study_pack import PACK, TOPICS, NOTES, VIDEOS
import shutil

out = Path("output/pdf"); out.mkdir(parents=True, exist_ok=True)
assets = Path("courses/content/pdfs"); assets.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont("Tahoma", "C:/Windows/Fonts/tahoma.ttf"))
pdfmetrics.registerFont(TTFont("TahomaBold", "C:/Windows/Fonts/tahomabd.ttf"))
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="BodyTahoma", fontName="Tahoma", fontSize=10.5, leading=15, spaceAfter=9))
styles.add(ParagraphStyle(name="TitleTahoma", fontName="TahomaBold", fontSize=21, leading=26, textColor=colors.HexColor("#123763"), spaceAfter=16))
styles.add(ParagraphStyle(name="HeadingTahoma", fontName="TahomaBold", fontSize=13, leading=17, spaceBefore=10, spaceAfter=7))
styles.add(ParagraphStyle(name="CodeTahoma", fontName="Courier", fontSize=8.5, leading=11, spaceAfter=10))

def paragraph(text):
    return Paragraph(escape(text).replace("\n", "<br/>"), styles["BodyTahoma"])

def footer(canvas, doc):
    canvas.setFont("Tahoma", 8)
    canvas.setFillColor(colors.HexColor("#526277"))
    canvas.drawString(42, 27, "ABI TECH | Level 200 ICT | DSA learning support")
    canvas.drawRightString(553, 27, str(doc.page))

def build(name, title, blocks):
    story=[Paragraph(escape(title),styles["TitleTahoma"])]
    for heading, body, code in blocks:
        if heading in {"Python practice", "Analysis plan"}: story.append(PageBreak())
        if heading: story.append(Paragraph(escape(heading),styles["HeadingTahoma"]))
        if body: story.append(paragraph(body))
        if code:
            wrapped="\n".join("\n".join(textwrap.wrap(line,width=91,replace_whitespace=False,drop_whitespace=False)) if len(line)>91 else line for line in code.splitlines())
            story.append(Preformatted(wrapped,styles["CodeTahoma"]))
    target=out/name
    SimpleDocTemplate(str(target),pagesize=(595.28,841.89),rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=45,title=title,author="ABI TECH project").build(story,onFirstPage=footer,onLaterPages=footer)
    shutil.copy2(target,assets/name)
    print(target)

for i, item in enumerate(PACK):
    build(f"dsa-topic-{i+1}.pdf",TOPICS[i],[
        ("Learning objectives",item["objectives"],None),
        ("Core concepts",NOTES[i],None),
        ("Worked example",item["worked"],None),
        ("Python practice", "Run this example in your own Python environment. Check the assertions, then extend the tests.",item["code"]),
        ("Practice questions",item["practice"],None),
        ("Self-check answers",item["answers"],None),
        ("Extension task",item["challenge"],None),
        ("Further study", "University lecture resource: " + VIDEOS[i],None),
    ])
build("pilot-guide.pdf","DSA pilot participation and evaluation guide",[
    ("Purpose","Evaluate usability and describe changes in topic-level assessment results among participating Level 200 ICT students. Approval of the score bands, assessment difficulty and real-participant pilot was reported by the project owner on 26 November 2026. Record the institutional approval reference and study arrangements before recruitment; this guide is not an ethics approval letter.",None),
    ("Before inviting participants","Confirm the DSA course lecturer, question bank and comparable-difficulty approval. Verify published learning resources and the live student journey on a phone and a computer. Select a participant target and provide a project contact through the lecturer. Demonstration accounts are synthetic and must not be recruited or included in research evidence.",None),
    ("Participant journey","1. Register using your own account and select the DSA course.\n2. Read the research participation information and decide freely whether to consent.\n3. Complete the diagnostic before using the recommended learning materials.\n4. Open My learning plan and study the suggested resources. Mark activities complete honestly.\n5. Complete the follow-up quiz and review the updated plan.\n6. Optionally complete the usability ratings. You may withdraw research participation without losing normal learning access.",None),
    ("Lecturer procedure","Explain the purpose and avoid coaching individual answers during either assessment. Use comparable conditions and record relevant disruptions. Review students' weak topics and give targeted feedback. Do not turn demonstration results into actual participant records. Record any differences in teaching time, assessment timing or assistance that may affect interpretation.",None),
    ("Analysis plan","Filter Evaluation by the pilot study, course and dates. Include only current consenting real participants and records from their consent date. Compare only matched approved diagnostic/follow-up pairs. Report participant counts, missing follow-ups, average pre/post scores, percentage-point change and the three usability ratings. Review topic-level results and resource activity. A comparison group can strengthen the design where feasible and approved; it is not automatically created by this system.",None),
    ("Interpretation and reporting","An observed score increase is descriptive evidence, not proof that the platform caused it. Discuss repeated-test effects, selection, attrition, instructional support and sample size. Report negative and unchanged results as well as positive results. No academic-effectiveness finding exists until real data have been collected and analysed.",None),
    ("Privacy and withdrawal","Research exports replace names with participant codes and omit email addresses and written answers. Access remains restricted to authorized staff. Withdrawal excludes a student from subsequent reports but cannot recall an exported report automatically. Follow the approved institutional retention and data-handling arrangements.",None),
])
