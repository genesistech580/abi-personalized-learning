import csv
import json
from datetime import datetime, time, timedelta
from functools import wraps
from time import perf_counter
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Q, F, Value
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_http_methods
from accounts.models import User
from assessments.models import DiagnosticAttempt, DiagnosticQuestion, PilotFeedback
from courses.models import Course, Enrollment, Lesson, LessonCompletion, LessonVisit, ResourceProgress
from .models import AuditEvent, ResearchConsent, ConsentEvent, ServiceStatus
from .chat import chat_configuration, save_chat_configuration, request_reply, ChatError, chat_mode, save_chat_mode
from .services import record_service

def administrator(view):

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.ADMINISTRATOR:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped

class Filters(forms.Form):
    q = forms.CharField(required=False, label='Search', max_length=150)
    course = forms.ModelChoiceField(queryset=Course.objects.order_by('code'), required=False)
    cohort = forms.CharField(required=False, max_length=80, label='Participant group')
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    status = forms.ChoiceField(required=False, choices=[('', 'All statuses'), ('active', 'Active'), ('inactive', 'Inactive / archived'), ('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')])

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and (data['start'] > data['end']):
            raise forms.ValidationError('Start date must be before the end date.')
        return data

def date_range(queryset, field, data):
    if data.get('start'):
        queryset = queryset.filter(**{field + '__gte': timezone.make_aware(datetime.combine(data['start'], time.min))})
    if data.get('end'):
        queryset = queryset.filter(**{field + '__lt': timezone.make_aware(datetime.combine(data['end'] + timedelta(days=1), time.min))})
    return queryset

def paged(request, rows):
    query = request.GET.copy()
    query.pop('page', None)
    return {'page_obj': Paginator(rows, 20).get_page(request.GET.get('page')), 'query': query.urlencode()}

def link(name, *args):
    return reverse(name, args=args)

class AIConfigurationForm(forms.Form):
    key = forms.CharField(label='OpenAI API key', max_length=512, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    model = forms.RegexField(label='Model', regex=r'^[A-Za-z0-9._:-]+$', max_length=100)

    def clean_key(self):
        key = self.cleaned_data['key'].strip()
        if not key.startswith('sk-') or any(char.isspace() for char in key):
            raise forms.ValidationError('Enter an API key without spaces or quotation marks.')
        return key


@administrator
def hub(request, section='students'):
    if request.method not in {'GET', 'POST'}:
        raise PermissionDenied
    if request.method == 'POST' and section != 'system':
        raise PermissionDenied
    ai_form = AIConfigurationForm(initial={'model': chat_configuration()[1]})
    if section == 'system' and request.method == 'POST':
        action = request.POST.get('action')
        if action == 'configure_chat_mode':
            mode = request.POST.get('mode')
            if mode not in {'free', 'openai'}:
                raise PermissionDenied
            save_chat_mode(mode)
            AuditEvent.objects.create(actor=request.user, actor_label=request.user.username, action='configure', model_label='service.chat', object_id='mode', fields=[mode])
            messages.success(request, 'Free course help enabled.' if mode == 'free' else 'OpenAI mode selected. API credit is required.')
            return redirect('admin_hub', section='system')
        if action == 'configure_ai':
            ai_form = AIConfigurationForm(request.POST)
            if ai_form.is_valid():
                try:
                    save_chat_configuration(ai_form.cleaned_data['key'], ai_form.cleaned_data['model'])
                except OSError:
                    ai_form.add_error(None, 'Configuration could not be saved. Check private server file permissions.')
                else:
                    AuditEvent.objects.create(actor=request.user, actor_label=request.user.username, action='configure', model_label='service.ai', object_id='configuration', fields=['key', 'model'])
                    messages.success(request, 'AI configuration saved. Use Test connection to verify it.')
                    return redirect('admin_hub', section='system')
        elif action == 'test_ai':
            if chat_mode() == 'free':
                messages.success(request, 'Free course help is enabled. No API key or credit is needed.')
                return redirect('admin_hub', section='system')
            try:
                request_reply([{'role': 'user', 'content': 'Reply with OK.'}], 'This is a connection check.', max_tokens=64)
            except ChatError as error:
                record_service('ai', False, 'AI connection check failed: ' + error.code + '.')
                messages.error(request, error.message)
            else:
                record_service('ai', True, 'AI connection check succeeded.')
                messages.success(request, 'AI connection succeeded. Chat is ready.')
            return redirect('admin_hub', section='system')
        else:
            raise PermissionDenied
    titles = {'students': 'Students', 'lecturers': 'Lecturers', 'courses': 'Courses', 'enrollments': 'Enrollments', 'content': 'Content oversight', 'consent': 'Research participation', 'audit': 'Audit history', 'system': 'System status'}
    if section not in titles:
        from django.http import Http404
        raise Http404
    form = Filters(request.GET)
    allowed = {'students': {'q', 'course', 'status'}, 'lecturers': {'q', 'course', 'status'},
               'courses': {'q', 'status'}, 'enrollments': {'q', 'course', 'status', 'start', 'end'},
               'content': {'q', 'course', 'status'}, 'consent': {'q', 'course', 'cohort'},
               'audit': {'q', 'start', 'end'}, 'system': set()}[section]
    for field in list(form.fields):
        if field not in allowed:
            form.fields.pop(field)
    if 'status' in form.fields:
        choices = {'students': [('active', 'Active'), ('inactive', 'Inactive')],
                   'lecturers': [('active', 'Active'), ('inactive', 'Inactive')],
                   'courses': [('active', 'Active'), ('archived', 'Archived')],
                   'enrollments': [('active', 'Active'), ('inactive', 'Withdrawn')],
                   'content': [('draft', 'Draft'), ('published', 'Published'), ('archived', 'Archived')]}
        form.fields['status'].choices = [('', 'All statuses')] + choices[section]
    valid = form.is_valid()
    data = form.cleaned_data if valid else {}
    q = data.get('q', '')
    selected = data.get('course')
    status = data.get('status')
    rows = []
    source_page = None
    if section in {'students', 'lecturers'}:
        people = User.objects.filter(role='student' if section == 'students' else 'lecturer', is_demo=False).order_by('username')
        if q:
            people = people.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(department__icontains=q))
        if selected:
            people = people.filter(enrollments__course=selected) if section == 'students' else people.filter(teaching_courses=selected)
        if status in {'active', 'inactive'}:
            people = people.filter(is_active=status == 'active')
        source_page = paged(request, people.distinct())
        for person in source_page['page_obj']:
            links = [('Edit', link('edit_account', person.pk)), ('Deactivate', link('delete_account', person.pk))]
            if section == 'students':
                links.insert(0, ('Progress', link('admin_student', person.pk)))
            rows.append({'label': person.username, 'detail': person.department, 'status': 'Active' if person.is_active else 'Inactive', 'links': links})
    elif section == 'courses':
        courses = Course.objects.select_related('lecturer').order_by('code')
        if q:
            courses = courses.filter(Q(code__icontains=q) | Q(title__icontains=q))
        if selected:
            courses = courses.filter(pk=selected.pk)
        if status in {'active', 'inactive', 'archived'}:
            courses = courses.filter(archived_at__isnull=status == 'active')
        source_page = paged(request, courses)
        for course in source_page['page_obj']:
            rows.append({'label': str(course), 'detail': course.lecturer.username, 'status': 'Archived' if course.archived_at else 'Active', 'links': [('Edit', link('edit_course', course.pk)), ('Students', link('course_report', course.pk)), ('Content', link('admin_hub', 'content') + '?course=' + str(course.pk)), ('Resources', link('course_resources', course.pk)), ('Restore' if course.archived_at else 'Archive', link('admin_course_state', course.pk)), ('Delete', link('permanent_delete_course', course.pk))]})
    elif section == 'enrollments':
        records = Enrollment.objects.filter(student__is_demo=False).select_related('course', 'student').order_by('course__code', 'student__username')
        if q:
            records = records.filter(Q(student__username__icontains=q) | Q(course__code__icontains=q))
        if selected:
            records = records.filter(course=selected)
        if status in {'active', 'inactive'}:
            records = records.filter(withdrawn_at__isnull=status == 'active')
        records = date_range(records, 'enrolled_at', data)
        source_page = paged(request, records)
        for enrollment in source_page['page_obj']:
            rows.append({'label': enrollment.student.username, 'detail': str(enrollment.course), 'status': 'Withdrawn' if enrollment.withdrawn_at else 'Active', 'links': [('Manage', link('admin_enrollment', enrollment.pk))]})
    elif section == 'content':
        queries = []
        for model, kind in [(Lesson, 'lesson'), (DiagnosticQuestion, 'question')]:
            items = model.objects.all().order_by()
            if selected:
                items = items.filter(course=selected)
            if status in {'draft', 'published', 'archived'}:
                items = items.filter(status=status)
            field = 'title' if kind == 'lesson' else 'prompt'
            if q:
                items = items.filter(**{field + '__icontains': q})
            queries.append(items.values('pk', 'course_id', 'status', label=F(field),
                course_code=F('course__code'), course_title=F('course__title'),
                kind=Value(kind), stage_label=Value('Lesson') if kind == 'lesson' else F('stage')))
        source_page = paged(request, queries[0].union(queries[1]).order_by('course_code', 'kind', 'pk'))
        for item in source_page['page_obj']:
            detail = item['course_code'] + ' · ' + item['course_title'] + ' · ' + item['stage_label']
            rows.append({'label': item['label'], 'detail': detail, 'status': item['status'].capitalize(),
                         'links': [('Preview', link('content_preview', item['kind'], item['pk'])), ('Edit', link('edit_content', item['kind'], item['pk']))]})
    elif section == 'consent':
        people = User.objects.filter(role='student', is_demo=False).select_related('researchconsent').order_by('username')
        if q:
            people = people.filter(username__icontains=q)
        if selected:
            people = people.filter(enrollments__course=selected)
        if data.get('cohort'):
            people = people.filter(researchconsent__cohort=data['cohort'])
        source_page = paged(request, people.distinct())
        for person in source_page['page_obj']:
            consent = getattr(person, 'researchconsent', None)
            state = 'Not given' if not consent or not consent.consented_at else 'Withdrawn' if consent.withdrawn_at else 'Consented'
            detail = consent.cohort if consent else 'No group'
            if consent and consent.consented_at:
                detail += ' · consent ' + consent.consented_at.strftime('%Y-%m-%d %H:%M')
            if consent and consent.withdrawn_at:
                detail += ' · withdrawn ' + consent.withdrawn_at.strftime('%Y-%m-%d %H:%M')
            rows.append({'label': person.username, 'detail': detail, 'status': state, 'links': [('Assign group', link('admin_cohort', person.pk))]})
    elif section == 'audit':
        events = AuditEvent.objects.all()
        if q:
            events = events.filter(Q(actor_label__icontains=q) | Q(model_label__icontains=q) | Q(object_id=q))
        events = date_range(events, 'created_at', data)
        source_page = paged(request, events)
        for event in source_page['page_obj']:
            rows.append({'label': f'{event.actor_label} · {event.action} · {event.model_label} #{event.object_id}', 'detail': event.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') + ' · ' + ', '.join(event.fields), 'links': []})
    context = {'title': titles[section], 'section': section, 'form': form}
    if source_page and valid:
        context.update(source_page)
        context['page_obj'].object_list = rows
    else:
        context.update(paged(request, rows if valid else []))
    if section == 'system':
        started = perf_counter()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        backup = {}
        try:
            backup = json.loads((settings.BASE_DIR / '.backup-status.json').read_text())
        except (OSError, ValueError):
            pass
        context['ai_form'] = ai_form
        context['ai_model'] = chat_configuration()[1]
        context['chat_mode'] = chat_mode()
        context['service_history'] = ServiceStatus.objects.order_by('service')
        context['backup_stale'] = not backup.get('verified_at') or timezone.now() - datetime.fromisoformat(backup['verified_at']) > timedelta(hours=36)
        context['services'] = {'database_ms': round(1000 * (perf_counter() - started), 1), 'email': bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD), 'ai': bool(chat_configuration()[0]), 'backup': backup}
    return render(request, 'dashboard/admin_hub.html', context)

@administrator
def student(request, pk):
    learner = get_object_or_404(User, pk=pk, role='student')
    records = Enrollment.objects.filter(student=learner).select_related('course').order_by('course__code')
    return render(request, 'dashboard/admin_student.html', {'title': 'Student progress', 'learner': learner, 'records': records})

class EnrollmentForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.filter(archived_at__isnull=True).order_by('code'))
    active = forms.BooleanField(required=False, label='Active enrollment')

@administrator
@require_http_methods(['GET', 'POST'])
def enrollment(request, pk):
    record = get_object_or_404(Enrollment.objects.filter(student__is_demo=False).select_related('course', 'student'), pk=pk)
    form = EnrollmentForm(request.POST if request.method == 'POST' else None, initial={'course': record.course_id, 'active': not record.withdrawn_at})
    form.fields['course'].queryset = Course.objects.filter(Q(archived_at__isnull=True) | Q(pk=record.course_id)).order_by('code')
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = Enrollment.objects.select_for_update().get(pk=pk)
            target = form.cleaned_data['course']
            active = form.cleaned_data['active']
            if target.pk != record.course_id:
                record.withdrawn_at = timezone.now()
                record.save(update_fields=['withdrawn_at'])
                target_record, _ = Enrollment.objects.get_or_create(course=target, student=record.student)
            else:
                target_record = record
            target_record.withdrawn_at = None if active else timezone.now()
            target_record.save(update_fields=['withdrawn_at'])
        messages.success(request, 'Enrollment updated. Previous course history retained.')
        return redirect('admin_hub', section='enrollments')
    return render(request, 'dashboard/create.html', {'title': 'Manage enrollment · ' + record.student.username, 'form': form})

@administrator
@require_http_methods(['GET', 'POST'])
def course_state(request, pk):
    course = get_object_or_404(Course, pk=pk)
    action = 'Restore' if course.archived_at else 'Archive'
    if request.method == 'POST':
        course.archived_at = None if course.archived_at else timezone.now()
        course.save(update_fields=['archived_at'])
        messages.success(request, 'Course updated. Learning history retained.')
        return redirect('admin_hub', section='courses')
    return render(request, 'dashboard/confirm.html', {'title': action + ' course', 'detail': str(course)})

@administrator
@require_http_methods(['GET', 'POST'])
def cohort(request, pk):
    learner = get_object_or_404(User, pk=pk, role='student')
    record = ResearchConsent.objects.filter(student=learner).first()

    class GroupForm(forms.Form):
        cohort = forms.CharField(max_length=80, required=False, label='Participant group')
    form = GroupForm(request.POST if request.method == 'POST' else None, initial={'cohort': record.cohort if record else ''})
    if request.method == 'POST' and form.is_valid():
        ResearchConsent.objects.update_or_create(student=learner, defaults={'cohort': form.cleaned_data['cohort']})
        messages.success(request, 'Group saved. Consent must be given by the student.')
        return redirect('admin_hub', section='consent')
    return render(request, 'dashboard/create.html', {'title': 'Participant group · ' + learner.username, 'form': form})

@login_required
@require_http_methods(['GET', 'POST'])
@transaction.atomic
def consent(request):
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied
    record = ResearchConsent.objects.select_for_update().filter(student=request.user).first()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'withdraw' and record and record.active:
            record.withdrawn_at = timezone.now()
            record.save(update_fields=['withdrawn_at'])
            ConsentEvent.objects.create(student=request.user, action='withdraw', information_version=record.information_version)
            messages.success(request, 'Research participation withdrawn.')
        elif action == 'consent' and request.POST.get('agree') == 'yes':
            if not record or not record.active:
                record, _ = ResearchConsent.objects.get_or_create(student=request.user)
                record.consented_at = timezone.now()
                record.withdrawn_at = None
                record.information_version = '2026-11-19'
                record.save()
                ConsentEvent.objects.create(student=request.user, action='consent', information_version=record.information_version)
                messages.success(request, 'Research consent recorded.')
        else:
            messages.error(request, 'Confirm the information before giving consent.')
        return redirect('research_consent')
    return render(request, 'dashboard/consent.html', {'consent': record, 'consent_history': ConsentEvent.objects.filter(student=request.user)[:20]})

def research_rows(data):
    consents = ResearchConsent.objects.filter(consented_at__isnull=False, withdrawn_at__isnull=True, student__is_active=True, student__is_demo=False)
    if data.get('cohort'):
        consents = consents.filter(cohort=data['cohort'])
    consent_by_student = {item.student_id: item for item in consents}
    attempts = DiagnosticAttempt.objects.filter(student__is_demo=False, student_id__in=consent_by_student).select_related('course').order_by('submitted_at', 'pk')
    if data.get('course'):
        attempts = attempts.filter(course=data['course'])
    attempts = date_range(attempts, 'submitted_at', data)
    histories = {}
    for attempt in attempts:
        if attempt.submitted_at >= consent_by_student[attempt.student_id].consented_at:
            histories.setdefault((attempt.course_id, attempt.student_id), []).append(attempt)
    enrollments = Enrollment.objects.filter(student_id__in=consent_by_student).select_related('course')
    if data.get('course'):
        enrollments = enrollments.filter(course=data['course'])
    codes = {attempt.course_id: attempt.course.code for history in histories.values() for attempt in history}
    for enrollment in enrollments:
        histories.setdefault((enrollment.course_id, enrollment.student_id), [])
        codes[enrollment.course_id] = enrollment.course.code
    rows = []
    for (course_id, student_id), history in histories.items():
        comparable = []
        for first in history:
            if first.stage != 'diagnostic' or not first.comparison_key or (not first.question_count):
                continue
            matches = [item for item in history if item.stage == 'followup' and item.pk > first.pk and (item.comparison_key == first.comparison_key) and item.question_count]
            if matches:
                comparable = [first, matches[-1]]
                break
        before = 100 * comparable[0].correct_count / comparable[0].question_count if comparable else None
        after = 100 * comparable[1].correct_count / comparable[1].question_count if comparable else None
        survey = PilotFeedback.objects.filter(student_id=student_id, course_id=course_id, updated_at__gte=consent_by_student[student_id].consented_at)
        survey = date_range(survey, 'updated_at', data).first()
        completions = date_range(LessonCompletion.objects.filter(student_id=student_id, lesson__course_id=course_id, completed_at__gte=consent_by_student[student_id].consented_at), 'completed_at', data).count()
        visits = date_range(LessonVisit.objects.filter(student_id=student_id, lesson__course_id=course_id, last_opened_at__gte=consent_by_student[student_id].consented_at), 'last_opened_at', data).count()
        resources_completed = date_range(ResourceProgress.objects.filter(student_id=student_id, resource__course_id=course_id, completed_at__gte=consent_by_student[student_id].consented_at), 'completed_at', data).count()
        resources_opened = date_range(ResourceProgress.objects.filter(student_id=student_id, resource__course_id=course_id, last_opened_at__gte=consent_by_student[student_id].consented_at), 'last_opened_at', data).count()
        rows.append({'resources_completed': resources_completed, 'resources_opened': resources_opened, 'participant': salted_hmac('research-export', str(student_id)).hexdigest()[:16], 'course': codes[course_id], 'attempts': len(history), 'completed': completions, 'visited': visits, 'before': before, 'after': after, 'change': after - before if comparable else None, 'ease': survey.ease if survey else '', 'clarity': survey.clarity if survey else '', 'usefulness': survey.usefulness if survey else ''})
    return rows


def research_model_metrics(data):
    attempts = DiagnosticAttempt.objects.filter(student__is_demo=False, 
        student__researchconsent__consented_at__isnull=False,
        student__researchconsent__withdrawn_at__isnull=True,
        student__is_active=True,
        submitted_at__gte=F('student__researchconsent__consented_at'),
    ).exclude(comparison_key='').select_related('course').order_by('submitted_at', 'pk')
    if data.get('course'):
        attempts = attempts.filter(course=data['course'])
    if data.get('cohort'):
        attempts = attempts.filter(student__researchconsent__cohort=data['cohort'])
    attempts = date_range(attempts, 'submitted_at', data)
    peers, predictions, evaluated, errors, codes = {}, {}, set(), {}, {}
    for attempt in attempts:
        course_id = attempt.course_id
        codes[course_id] = attempt.course.code
        key = (course_id, attempt.student_id, attempt.comparison_key)
        if attempt.stage == 'diagnostic' and key not in predictions:
            predicted_topics = {}
            for topic, result in attempt.results.items():
                pool_key = (course_id, attempt.comparison_key, topic)
                other = [value for student_id, value in peers.get(pool_key, {}).items() if student_id != attempt.student_id]
                total = sum(value['total'] for value in other)
                if total and result['total']:
                    prior = sum(value['correct'] for value in other) / total
                    predicted_topics[topic] = (result['correct'] / result['total'], (result['correct'] + 2 * prior) / (result['total'] + 2))
                peers.setdefault(pool_key, {})[attempt.student_id] = result
            predictions[key] = predicted_topics
        elif attempt.stage == 'followup' and key in predictions and key not in evaluated:
            evaluated.add(key)
            for topic, (baseline, prediction) in predictions[key].items():
                observed = attempt.results.get(topic)
                if observed and observed['total']:
                    actual = observed['correct'] / observed['total']
                    errors.setdefault(course_id, []).append((abs(baseline - actual), abs(prediction - actual), attempt.student_id))
    metrics = []
    for course_id, code in codes.items():
        values = errors.get(course_id, [])
        count = len(values)
        learners = len({value[2] for value in values})
        baseline = 100 * sum(value[0] for value in values) / count if count else None
        model = 100 * sum(value[1] for value in values) / count if count else None
        metrics.append({'course': code, 'count': count, 'learners': learners, 'baseline': baseline, 'model': model,
                        'supported': count >= 10 and learners >= 5 and model < baseline})
    return metrics

@administrator
def evaluation(request):
    form = Filters(request.GET)
    form.fields.pop('q')
    form.fields.pop('status')
    valid = form.is_valid()
    rows = research_rows(form.cleaned_data) if valid else []
    if request.GET.get('export') == 'csv' and valid:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="learning-evaluation.csv"'
        response['Cache-Control'] = 'private, no-store'
        writer = csv.writer(response)
        keys = ['participant', 'course', 'attempts', 'completed', 'visited', 'resources_completed', 'resources_opened', 'before', 'after', 'change', 'ease', 'clarity', 'usefulness']
        writer.writerow(keys)
        for row in rows:
            values = [row[key] for key in keys]
            writer.writerow([("'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value) if isinstance(value, str) else value for value in values])
        AuditEvent.objects.create(actor=request.user, actor_label=request.user.username, action='export', model_label='research.report', object_id='filtered', fields=['deidentified_csv'])
        return response
    changes = [row['change'] for row in rows if row['change'] is not None]
    context = {'title': 'Evaluation', 'form': form, 'pair_count': len(changes), 'change': sum(changes) / len(changes) if changes else None, 'participants': len({row['participant'] for row in rows})}
    context['model_metrics'] = research_model_metrics(form.cleaned_data) if valid else []
    context.update(paged(request, rows))
    return render(request, 'dashboard/admin_evaluation.html', context)
