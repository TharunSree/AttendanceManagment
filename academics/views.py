# In academics/views.py
import csv
import json
import calendar
from datetime import datetime
from itertools import chain

from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models import ExpressionWrapper, fields, F, Q
from django.db.models.functions import TruncMonth
from django.forms import inlineformset_factory, formset_factory
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django import forms
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from academics.forms import EditStudentForm, AttendanceSettingsForm, TimeSlotForm, MarkAttendanceForm, \
    TimetableEntryForm, SubstitutionForm, AttendanceReportForm, AnnouncementForm, CriterionFormSet, MarkingSchemeForm, \
    MarkSelectForm, BulkMarksImportForm, MarksReportForm, ExtraClassForm
from accounts.models import Profile
from .forms import StudentGroupForm, CourseForm, AddStudentForm, SubjectForm
from .models import StudentGroup, AttendanceSettings, Course, Subject, \
    Timetable, AttendanceRecord, CourseSubject, TimeSlot, ClassCancellation, DailySubstitution, Announcement, \
    UserNotificationStatus, MarkingScheme, Mark, Criterion, ExtraClass
from accounts.decorators import nav_item
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment


# ... other views ...

@login_required
@permission_required('academics.view_attendance_settings', raise_exception=True)
@nav_item(title="Attendance Settings", icon="iconsminds-gears", url_name="academics:admin_settings",
          permission='academics.view_attendance_settings', group='application_settings', order=1)
def admin_settings_view(request):
    timeslot_form = TimeSlotForm()
    settings_obj = AttendanceSettings.load()
    settings_form = AttendanceSettingsForm(instance=settings_obj)

    if request.method == 'POST':
        # Check which form was submitted based on the button's name attribute
        if 'submit_timeslot' in request.POST:
            timeslot_form = TimeSlotForm(request.POST)
            if timeslot_form.is_valid():
                timeslot_form.save()
                messages.success(request, "New time slot has been created.")
                return redirect('academics:admin_settings')

        elif 'submit_settings' in request.POST:
            settings_form = AttendanceSettingsForm(request.POST, instance=settings_obj)
            if settings_form.is_valid():
                settings_form.save()
                messages.success(request, "Attendance settings have been updated.")
                return redirect('academics:admin_settings')

    timeslots = TimeSlot.objects.all()
    context = {
        'timeslots': timeslots,
        'timeslot_form': timeslot_form,
        'settings_form': settings_form
    }
    return render(request, 'academics/admin_settings.html', context)


# In academics/views.py

@login_required
@permission_required('auth.view_user', raise_exception=True)
def admin_student_list_view(request, group_id):
    student_group = get_object_or_404(StudentGroup, pk=group_id)
    students = User.objects.filter(
        profile__student_group=student_group, profile__role='student'
    ).select_related('profile').order_by('first_name', 'last_name')

    settings = AttendanceSettings.load()
    required_percentage = settings.required_percentage

    # Determine the latest semester to calculate attendance against
    latest_semester_num = CourseSubject.objects.filter(
        course=student_group.course
    ).order_by('-semester').values_list('semester', flat=True).first()

    students_with_attendance = []
    if latest_semester_num:
        for student in students:
            # This logic calculates the attendance percentage for each student
            subjects_for_semester = CourseSubject.objects.filter(
                course=student_group.course, semester=latest_semester_num
            )
            total_classes = AttendanceRecord.objects.filter(
                timetable__student_group=student_group,
                timetable__subject__in=subjects_for_semester
            ).values('date', 'timetable_id').distinct().count()

            student_records = AttendanceRecord.objects.filter(
                student=student, timetable__subject__in=subjects_for_semester
            )
            present_count = student_records.filter(status='Present').count()

            percentage = (present_count / total_classes * 100) if total_classes > 0 else None

            students_with_attendance.append({
                'student': student,
                'attendance_percentage': percentage
            })
    else:
        # If no semester, just list students without attendance data
        students_with_attendance = [{'student': s, 'attendance_percentage': None} for s in students]

    # --- FIX STARTS HERE ---

    # 1. Check the GET parameter from the form submission
    show_low_attendance_only = request.GET.get('low_attendance_filter') == 'on'

    # 2. If the filter is active, rebuild the list with only matching students
    if show_low_attendance_only:
        students_with_attendance = [
            item for item in students_with_attendance
            if item['attendance_percentage'] is not None and item['attendance_percentage'] < required_percentage
        ]

    # --- FIX ENDS HERE ---

    context = {
        'student_group': student_group,
        'students_with_attendance': students_with_attendance,
        'total_students': students.count(),
        'latest_semester_num': latest_semester_num,
        'required_percentage': required_percentage,
        # 3. Pass the flag back to the template to keep the checkbox state
        'show_low_attendance_only': show_low_attendance_only,
    }
    return render(request, 'academics/admin_student_list.html', context)


@login_required
@permission_required('academics.view_studentgroup', raise_exception=True)
@nav_item(title="Manage Classes", icon="iconsminds-network", url_name="academics:admin_select_class",
          permission='academics.view_studentgroup', group='admin_management', order=30)
def admin_select_class_view(request):
    """
    This view fetches all existing classes (StudentGroup) from the database
    and passes them to the template, so the admin can choose one.
    """
    # .select_related() is a performance optimization that fetches the
    # related course and session in the same database query.
    student_groups = StudentGroup.objects.all().select_related('course')

    context = {
        'student_groups': student_groups,
    }
    return render(request, 'academics/admin_select_class.html', context)


@login_required
@permission_required('academics.view_attendancerecord')  # Or a more general permission
def admin_student_attendance_detail_view(request, student_id):
    student = get_object_or_404(User, pk=student_id, profile__role='student')
    student_group = student.profile.student_group if hasattr(student, 'profile') else None

    # --- Get view type and filters from request ---
    view_type = request.GET.get('view_type', 'semester')
    selected_semester = request.GET.get('semester')
    selected_month_str = request.GET.get('month')
    selected_date_str = request.GET.get('date', timezone.now().strftime('%Y-%m-%d'))

    # --- Initialize context dictionary ---
    context = {
        'student': student, 'student_group': student_group, 'view_type': view_type,
        'available_semesters': [], 'selected_semester': None,
        'subject_attendance_data': [], 'subject_attendance_data_json': '[]',
        'overall_attended_sem': 0, 'overall_absent_sem': 0, 'overall_percentage_sem': 0,
        'monthly_subject_data': [], 'monthly_subject_data_json': '[]',
        'available_months': [], 'selected_month': selected_month_str,
        'overall_attended_month': 0, 'overall_absent_month': 0, 'overall_percentage_month': 0,
        'daily_attendance_data': [], 'selected_date': selected_date_str,
        'marks_data': {}
    }

    if student_group and student_group.course:
        all_course_subjects_qs = CourseSubject.objects.filter(course=student_group.course)
        context['available_semesters'] = all_course_subjects_qs.values_list('semester', flat=True).distinct().order_by(
            'semester')

        if not selected_semester and context['available_semesters']:
            selected_semester = context['available_semesters'].last()
        context['selected_semester'] = int(selected_semester) if selected_semester and str(
            selected_semester).isdigit() else None

        if context['selected_semester']:
            # This base queryset gets ALL of the student's attendance records for the semester,
            # regardless of whether they are from a regular class or an extra class.
            student_records_sem = AttendanceRecord.objects.filter(
                student=student
            ).filter(
                Q(timetable__subject__semester=context['selected_semester']) |
                Q(extra_class__subject__semester=context['selected_semester'])
            )

            if view_type == 'semester':
                subjects_for_semester = all_course_subjects_qs.filter(semester=context['selected_semester'])
                for cs in subjects_for_semester:
                    # Calculate total conducted classes by combining regular and extra classes.
                    # This counts distinct sessions for which attendance was marked.
                    regular_classes_count = AttendanceRecord.objects.filter(
                        timetable__student_group=student_group, timetable__subject=cs
                    ).values('date', 'timetable__time_slot').distinct().count()

                    extra_classes_count = ExtraClass.objects.filter(
                        class_group=student_group, subject=cs
                    ).count()

                    total_classes = regular_classes_count + extra_classes_count

                    if total_classes > 0:
                        # Count attended classes from the pre-filtered student records
                        present_count = student_records_sem.filter(
                            Q(timetable__subject=cs) | Q(extra_class__subject=cs),
                            status__in=['Present', 'Late']
                        ).count()
                        absent_count = total_classes - present_count
                        context['subject_attendance_data'].append({
                            'subject_pk': cs.subject.pk, 'subject_name': cs.subject.name,
                            'attended_classes': present_count, 'absent_classes': absent_count,
                            'total_classes': total_classes,
                            'official_percentage': round(
                                (present_count / total_classes * 100) if total_classes > 0 else 0, 2)
                        })

                # Calculate overall semester stats after the loop
                context['overall_attended_sem'] = sum(d['attended_classes'] for d in context['subject_attendance_data'])
                total_sem = sum(d['total_classes'] for d in context['subject_attendance_data'])
                context['overall_absent_sem'] = total_sem - context['overall_attended_sem']
                context['overall_percentage_sem'] = round(
                    (context['overall_attended_sem'] / total_sem * 100) if total_sem > 0 else 0, 2)
                context['subject_attendance_data_json'] = json.dumps(context['subject_attendance_data'])

            elif view_type == 'monthly':
                # Get all records for the group in the semester to determine available months
                all_group_records = AttendanceRecord.objects.filter(
                    Q(timetable__student_group=student_group) | Q(extra_class__class_group=student_group),
                    Q(timetable__subject__semester=context['selected_semester']) | Q(
                        extra_class__subject__semester=context['selected_semester'])
                ).distinct()

                context['available_months'] = all_group_records.annotate(month=TruncMonth('date')).values(
                    'month').distinct().order_by('-month')

                if not selected_month_str and context['available_months']:
                    selected_month_str = context['available_months'][0]['month'].strftime('%Y-%m')
                context['selected_month'] = selected_month_str

                if selected_month_str:
                    year, month = map(int, selected_month_str.split('-'))
                    subjects_for_semester = all_course_subjects_qs.filter(semester=context['selected_semester'])
                    for cs in subjects_for_semester:
                        # Calculate total classes for the month (regular + extra)
                        regular_classes_month = AttendanceRecord.objects.filter(
                            timetable__student_group=student_group, timetable__subject=cs, date__year=year,
                            date__month=month
                        ).values('date', 'timetable__time_slot').distinct().count()

                        extra_classes_month = ExtraClass.objects.filter(
                            class_group=student_group, subject=cs, date__year=year, date__month=month
                        ).count()

                        total_classes_month = regular_classes_month + extra_classes_month

                        if total_classes_month > 0:
                            # Calculate present count for the month (regular + extra)
                            present_count_month = student_records_sem.filter(
                                Q(timetable__subject=cs) | Q(extra_class__subject=cs),
                                status__in=['Present', 'Late'], date__year=year, date__month=month
                            ).count()
                            absent_count_month = total_classes_month - present_count_month
                            context['monthly_subject_data'].append({
                                'subject_pk': cs.subject.pk, 'subject_name': cs.subject.name,
                                'attended_classes': present_count_month, 'absent_classes': absent_count_month,
                                'total_classes': total_classes_month,
                                'official_percentage': round(
                                    (present_count_month / total_classes_month * 100) if total_classes_month > 0 else 0,
                                    2)
                            })

                    # Calculate overall monthly stats after the loop
                    context['overall_attended_month'] = sum(
                        d['attended_classes'] for d in context['monthly_subject_data'])
                    total_month = sum(d['total_classes'] for d in context['monthly_subject_data'])
                    context['overall_absent_month'] = total_month - context['overall_attended_month']
                    context['overall_percentage_month'] = round(
                        (context['overall_attended_month'] / total_month * 100) if total_month > 0 else 0, 2)
                    context['monthly_subject_data_json'] = json.dumps(context['monthly_subject_data'])

            elif view_type == 'daily':
                try:
                    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
                    # Fetch all records for the day and prefetch related data for efficiency
                    daily_records = student_records_sem.filter(date=selected_date).select_related(
                        'timetable__subject__subject', 'timetable__time_slot',
                        'extra_class__subject__subject', 'extra_class__time_slot'
                    )

                    unified_daily_data = []
                    for record in daily_records:
                        if record.timetable:
                            unified_daily_data.append({
                                'subject_name': record.timetable.subject.subject.name,
                                'time_slot': record.timetable.time_slot,
                                'status': record.status,
                                'is_late': record.is_late
                            })
                        elif record.extra_class:
                            unified_daily_data.append({
                                'subject_name': record.extra_class.subject.subject.name,
                                'time_slot': record.extra_class.time_slot,
                                'status': record.status,
                                'is_late': record.is_late
                            })

                    # Sort the final list by the start time of the time slot
                    unified_daily_data.sort(key=lambda x: x['time_slot'].start_time)
                    context['daily_attendance_data'] = unified_daily_data

                except (ValueError, TypeError):
                    pass  # Ignore invalid date formats


            elif view_type == 'marks':

                # Pass the ordered queryset of marks directly to the template.

                # The .order_by() is important for grouping in the template.

                context['marks_data_list'] = Mark.objects.filter(

                    student=student,

                    subject__semester=context['selected_semester']

                ).select_related(

                    'subject__subject', 'criterion'

                ).order_by('subject__subject__name', 'criterion__name')

    return render(request, 'academics/admin_student_attendance_detail.html', context)


@login_required
@permission_required('academics.add_studentgroup', raise_exception=True)
def student_group_create_view(request):
    if request.method == 'POST':
        form = StudentGroupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'New class has been created successfully.')
            return redirect('academics:admin_select_class')
    else:
        form = StudentGroupForm()

    context = {
        'form': form,
        'form_title': 'Add New Class / Batch'
    }
    return render(request, 'academics/student_group_form.html', context)


@login_required
@permission_required('academics.update_studentgroup', raise_exception=True)
def student_group_update_view(request, pk):
    student_group = get_object_or_404(StudentGroup, pk=pk)
    if request.method == 'POST':
        form = StudentGroupForm(request.POST, instance=student_group)
        if form.is_valid():
            form.save()
            messages.success(request, f'Class "{student_group.name}" has been updated.')
            return redirect('academics:admin_select_class')
    else:
        form = StudentGroupForm(instance=student_group)

    context = {
        'form': form,
        'form_title': f'Edit Class: {student_group.name}'
    }
    return render(request, 'academics/student_group_form.html', context)


@login_required
@permission_required('academics.view_course', raise_exception=True)
@nav_item(title="Manage Courses", icon="iconsminds-books", url_name='academics:course_list',
          permission='academics.view_course', group='admin_management', order=10)
def course_list_view(request):
    courses = Course.objects.all()
    return render(request, 'academics/course_list.html', {'courses': courses})


@login_required
@permission_required('academics.add_course', raise_exception=True)
def course_create_view(request):
    # We define our inline formset here
    CourseSubjectFormSet = inlineformset_factory(
        Course, CourseSubject,
        fields=('subject', 'semester'),
        extra=1,  # Start with one extra form
        can_delete=True,
        widgets={
            'subject': forms.Select(attrs={'class': 'custom-select'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    )

    if request.method == 'POST':
        form = CourseForm(request.POST)
        formset = CourseSubjectFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                course = form.save()
                formset.instance = course
                formset.save()
                messages.success(request, 'Course and subjects saved successfully.')
                return redirect('academics:course_list')
    else:
        form = CourseForm()
        formset = CourseSubjectFormSet()

    context = {
        'form': form,
        'formset': formset,
        'form_title': 'Create New Course'
    }
    return render(request, 'academics/course_form_with_subjects.html', context)


@login_required
@permission_required('academics.update_course', raise_exception=True)
def course_update_view(request, pk):
    course = get_object_or_404(Course, pk=pk)
    CourseSubjectFormSet = inlineformset_factory(
        Course, CourseSubject,
        fields=('subject', 'semester'),
        extra=1,
        can_delete=True,
        widgets={
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'semester': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    )

    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        formset = CourseSubjectFormSet(request.POST, instance=course)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                messages.success(request, 'Course and subjects updated successfully.')
                return redirect('academics:course_list')
    else:
        form = CourseForm(instance=course)
        formset = CourseSubjectFormSet(instance=course)

    context = {
        'form': form,
        'formset': formset,
        'form_title': f'Edit Course: {course.name}'
    }
    return render(request, 'academics/course_form_with_subjects.html', context)


@login_required
@permission_required('academics.delete_course', raise_exception=True)
def course_delete_view(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Course deleted successfully.')
        return redirect('academics:course_list')
    return render(request, 'academics/course_confirm_delete.html', {'course': course})


@login_required
@permission_required('academics.delete_studentgroup', raise_exception=True)
def student_group_delete_view(request, pk):
    student_group = get_object_or_404(StudentGroup, pk=pk)
    if request.method == 'POST':
        student_group.delete()
        messages.success(request, 'Class deleted successfully.')
        return redirect('academics:admin_select_class')
    return render(request, 'academics/student_group_confirm_delete.html', {'student_group': student_group})


@login_required
@permission_required('academics.add_student', raise_exception=True)
@transaction.atomic
def student_create_view(request, group_id):
    student_group = get_object_or_404(StudentGroup, pk=group_id)
    if request.method == 'POST':
        form = AddStudentForm(request.POST, request.FILES)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'], email=form.cleaned_data['email'],
                password=form.cleaned_data['password'], first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name']
            )
            profile = user.profile
            profile.role = 'student'
            profile.student_id_number = form.cleaned_data['student_id_number']
            profile.contact_number = form.cleaned_data['contact_number']
            profile.student_group = student_group
            profile.photo = form.cleaned_data.get('photo')
            profile.father_name = form.cleaned_data.get('father_name')
            profile.father_phone = form.cleaned_data.get('father_phone')
            profile.mother_name = form.cleaned_data.get('mother_name')
            profile.mother_phone = form.cleaned_data.get('mother_phone')
            profile.address = form.cleaned_data.get('address')
            profile.save()
            messages.success(request, f"Student '{user.username}' created.")
            if '_addanother' in request.POST:
                return redirect('academics:student_create', group_id=group_id)
            else:
                return redirect('academics:admin_student_list', group_id=group_id)
    else:
        form = AddStudentForm()
    context = {'form': form, 'form_title': f'Add New Student to {student_group.name}', 'student_group': student_group}
    return render(request, 'academics/student_form.html', context)


@login_required
@permission_required('academics.delete_student', raise_exception=True)
def student_delete_view(request, pk):
    student = get_object_or_404(User, pk=pk)
    # Find the group ID before deleting the student to redirect back correctly
    student_group = student.student_groups.first()
    group_id = student_group.id if student_group else None

    if request.method == 'POST':
        # The associated Profile will be deleted automatically due to on_delete=models.CASCADE
        student.delete()
        messages.success(request, 'Student deleted successfully.')
        if group_id:
            return redirect('academics:admin_student_list', group_id=group_id)
        return redirect('home')  # Fallback redirect

    return render(request, 'academics/student_confirm_delete.html', {'student': student})


@login_required
@permission_required('academics.delete_studentgroup', raise_exception=True)
def student_group_delete_view(request, pk):
    student_group = get_object_or_404(StudentGroup, pk=pk)
    if request.method == 'POST':
        student_group.delete()
        messages.success(request, f'Class "{student_group.name}" has been deleted.')
        return redirect('academics:admin_select_class')
    return render(request, 'academics/student_group_confirm_delete.html', {'student_group': student_group})


@login_required
@permission_required('academics.delete_student', raise_exception=True)
def student_delete_view(request, pk):
    student = get_object_or_404(User, pk=pk)
    student_group = student.student_groups.first()  # To redirect back to the correct class list

    if request.method == 'POST':
        student.delete()
        messages.success(request, f'Student "{student.username}" has been deleted.')
        if student_group:
            return redirect('academics:admin_student_list', group_id=student_group.id)
        return redirect('academics:admin_select_class')  # Fallback

    return render(request, 'academics/confirm_delete.html', {'item': student, 'type': 'Student'})


@login_required
@permission_required('academics.view_subject', raise_exception=True)
@nav_item(title="Manage Subjects", icon="iconsminds-book", url_name='academics:subject_list',
          permission='academics.view_subject', group='admin_management', order=20)
def subject_list_view(request):
    subjects = Subject.objects.all().order_by('name')
    return render(request, 'academics/subject_list.html', {'subjects': subjects})


@login_required
@permission_required('academics.add_subject', raise_exception=True)
def subject_create_view(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject created successfully.')
            return redirect('academics:subject_list')
    else:
        form = SubjectForm()
    return render(request, 'academics/subject_form.html', {'form': form, 'form_title': 'Create New Subject'})


@login_required
@permission_required('academics.update_subject', raise_exception=True)
def subject_update_view(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject updated successfully.')
            return redirect('academics:subject_list')
    else:
        form = SubjectForm(instance=subject)
    return render(request, 'academics/subject_form.html', {'form': form, 'form_title': f'Edit Subject: {subject.name}'})


@login_required
@permission_required('academics.delete_subject', raise_exception=True)
def subject_delete_view(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted successfully.')
        return redirect('academics:subject_list')
    return render(request, 'academics/confirm_delete.html', {'item': subject, 'type': 'Subject'})


@login_required
@permission_required('academics.update_student', raise_exception=True)
def student_update_view(request, pk):
    student_user = get_object_or_404(User, pk=pk, profile__role='student')
    if request.method == 'POST':
        form = EditStudentForm(request.POST, request.FILES, instance=student_user.profile)
        if form.is_valid():
            form.save()
            student_user.first_name = form.cleaned_data['first_name']
            student_user.last_name = form.cleaned_data['last_name']
            student_user.email = form.cleaned_data['email']
            student_user.save()
            messages.success(request, 'Student details updated successfully.')
            return redirect('academics:student_profile', student_id=student_user.pk)
    else:
        form = EditStudentForm(instance=student_user.profile, initial={
            'first_name': student_user.first_name, 'last_name': student_user.last_name, 'email': student_user.email
        })
    context = {'form': form, 'form_title': f'Edit Student: {student_user.get_full_name()}', 'student': student_user}
    return render(request, 'academics/student_form.html', context)


@login_required
@permission_required('academics.delete_timeslot', raise_exception=True)
def timeslot_delete_view(request, pk):
    timeslot = get_object_or_404(TimeSlot, pk=pk)
    if request.method == 'POST':
        timeslot.delete()
        messages.success(request, "Time slot has been deleted.")
    return redirect('academics:admin_settings')


@login_required
@permission_required('academics.add_attendancerecord', raise_exception=True)
@nav_item(title="Daily Schedule", icon="simple-icon-check", url_name="academics:faculty_schedule",
          permission='academics.add_attendancerecord', group='faculty_tools', order=10)
def faculty_daily_schedule_view(request):
    # ... (The auto-cancellation logic at the beginning remains the same) ...

    current_day = timezone.now().strftime('%A')
    current_date = timezone.now().date()

    # --- CHANGE: Create a unified schedule list ---
    unified_schedule = []

    # 1. Get regularly scheduled classes
    regular_schedule = Timetable.objects.filter(
        faculty=request.user, day_of_week=current_day
    ).select_related('time_slot', 'subject__subject', 'student_group')

    # 2. Get classes this user is substituting for today
    substitutions = DailySubstitution.objects.filter(
        substituted_by=request.user, date=current_date
    ).select_related('timetable__time_slot', 'timetable__subject__subject', 'timetable__student_group')

    # 3. Get extra classes scheduled for today
    extra_classes_today = ExtraClass.objects.filter(
        teacher=request.user, date=current_date
    ).select_related('time_slot', 'subject__subject', 'class_group')

    # Get IDs of sessions cancelled today for quick lookup
    cancelled_today_ids = ClassCancellation.objects.filter(
        date=current_date
    ).values_list('timetable_id', flat=True)

    # Process regular and substituted classes
    processed_timetable_ids = set()
    for entry in regular_schedule:
        unified_schedule.append({
            'session': entry, 'type': 'regular', 'is_substitution': False,
            'is_cancelled': entry.id in cancelled_today_ids
        })
        processed_timetable_ids.add(entry.id)

    for sub in substitutions:
        if sub.timetable.id not in processed_timetable_ids:
            unified_schedule.append({
                'session': sub.timetable, 'type': 'regular', 'is_substitution': True,
                'is_cancelled': sub.timetable.id in cancelled_today_ids
            })

    # Process extra classes
    for extra_class in extra_classes_today:
        unified_schedule.append({
            'session': extra_class, 'type': 'extra', 'is_substitution': False,
            'is_cancelled': False  # Extra classes cannot be "cancelled" in the same way
        })

    # Sort the final combined list by time
    unified_schedule.sort(key=lambda x: x['session'].time_slot.start_time)

    context = {
        'schedule': unified_schedule,
        'current_day': current_day,
    }
    return render(request, 'academics/faculty_schedule.html', context)


@login_required
@permission_required('academics.add_attendancerecord', raise_exception=True)
def mark_extra_class_attendance_view(request, extra_class_id):
    current_date = timezone.now().date()
    extra_class_entry = get_object_or_404(ExtraClass, pk=extra_class_id)
    print(extra_class_entry)

    # Security check: ensure the logged-in user is the teacher for this extra class
    if extra_class_entry.teacher != request.user:
        raise PermissionDenied("You are not authorized to mark attendance for this class.")

    students = User.objects.filter(profile__student_group=extra_class_entry.class_group).order_by('first_name')
    MarkAttendanceFormSet = formset_factory(MarkAttendanceForm, extra=0)

    if request.method == 'POST':
        formset = MarkAttendanceFormSet(request.POST)
        if formset.is_valid():
            with transaction.atomic():
                for form in formset:
                    student_id = form.cleaned_data['student_id']
                    status = form.cleaned_data['status']
                    is_late = form.cleaned_data.get('is_late', False)
                    student = User.objects.get(pk=student_id)

                    # --- CHANGE: Save record with extra_class foreign key ---
                    record, created = AttendanceRecord.objects.update_or_create(
                        student=student,
                        extra_class=extra_class_entry,
                        date=current_date,
                        defaults={'status': status, 'is_late': is_late, 'marked_by': request.user}
                    )
            messages.success(request, "Attendance for the extra class has been marked successfully.")
            return redirect('academics:faculty_schedule')
    else:
        initial_data = []
        existing_records = AttendanceRecord.objects.filter(extra_class=extra_class_entry, date=current_date)
        status_map = {record.student_id: (record.status, record.is_late) for record in existing_records}
        for student in students:
            saved_status, saved_is_late = status_map.get(student.id, ('Present', False))
            initial_data.append({'student_id': student.id, 'status': saved_status, 'is_late': saved_is_late})
        formset = MarkAttendanceFormSet(initial=initial_data)

    student_forms = zip(students, formset)
    context = {
        # --- FIX: Use 'timetable_entry' as the key to match the reused template ---
        'session_object': extra_class_entry,
        'formset': formset,
        'student_forms': student_forms,
        'date': current_date,
        'is_extra_class': True  # This flag is still useful for conditional logic in the template
    }
    # We can reuse the existing mark_attendance.html template
    return render(request, 'academics/mark_attendance.html', context)


@login_required
@permission_required('academics.add_attendancerecord', raise_exception=True)
def mark_attendance_view(request, timetable_id, date_str=None):
    if date_str:
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        current_date = timezone.now().date()

    timetable_entry = get_object_or_404(Timetable, pk=timetable_id)
    students = User.objects.filter(profile__student_group=timetable_entry.student_group).order_by('first_name')

    MarkAttendanceFormSet = formset_factory(MarkAttendanceForm, extra=0)

    is_cancelled = ClassCancellation.objects.filter(timetable=timetable_entry, date=current_date).exists()
    if is_cancelled:
        messages.warning(request, "This class session was marked as not conducted, so attendance cannot be taken.")
        return redirect('academics:faculty_schedule')

    if request.method == 'POST':
        formset = MarkAttendanceFormSet(request.POST)
        if formset.is_valid():
            with transaction.atomic():
                for form in formset:
                    student_id = form.cleaned_data['student_id']
                    status = form.cleaned_data['status']
                    is_late = form.cleaned_data.get('is_late', False)  # Get the checkbox value
                    student = User.objects.get(pk=student_id)

                    record, created = AttendanceRecord.objects.get_or_create(
                        student=student,
                        timetable=timetable_entry,
                        date=current_date,
                        defaults={'status': status, 'is_late': is_late, 'marked_by': request.user}
                    )

                    if not created:
                        record.status = status
                        record.is_late = is_late  # Update the is_late field on edit
                        record.marked_by = request.user
                        record.save()

            messages.success(request, "Attendance has been marked successfully.")
            return redirect('academics:faculty_schedule')
    else:
        # This logic now also fetches the is_late status to pre-fill the form
        initial_data = []
        existing_records = AttendanceRecord.objects.filter(timetable=timetable_entry, date=current_date)
        status_map = {record.student_id: (record.status, record.is_late) for record in existing_records}
        for student in students:
            saved_status, saved_is_late = status_map.get(student.id, ('Present', False))
            initial_data.append({
                'student_id': student.id,
                'status': saved_status,
                'is_late': saved_is_late,
            })
        formset = MarkAttendanceFormSet(initial=initial_data)

    student_forms = zip(students, formset)
    context = {
        'session_object': timetable_entry,
        'formset': formset,
        'student_forms': student_forms,
        'date': current_date,
        'is_extra_class' : False,
    }
    return render(request, 'academics/mark_attendance.html', context)


@login_required
@permission_required('academics.add_classcancellation', raise_exception=True)
def class_cancellation_view(request, timetable_id):
    timetable_entry = get_object_or_404(Timetable, pk=timetable_id)
    if request.method == 'POST':
        # Create a cancellation record for this class on this day
        ClassCancellation.objects.get_or_create(
            timetable=timetable_entry,
            date=timezone.now().date(),
            defaults={'cancelled_by': request.user}
        )
        messages.info(request,
                      f"Class '{timetable_entry.subject.subject.name}' has been marked as not conducted for today.")
        return redirect('academics:faculty_schedule')

    # Redirect if accessed via GET
    return redirect('academics:faculty_schedule')


@login_required
@permission_required('academics.view_attendancerecord', raise_exception=True)
@nav_item(title="Daily Activity Log", icon="iconsminds-folder-open", url_name="academics:daily_log",
          permission='academics.view_attendancerecord', group='admin_management', order=40)
def daily_attendance_log_view(request):
    # Get all distinct dates from both attendance and cancellation records
    attendance_dates = AttendanceRecord.objects.values_list('date', flat=True)
    cancellation_dates = ClassCancellation.objects.values_list('date', flat=True)
    all_dates = sorted(list(set(chain(attendance_dates, cancellation_dates))), reverse=True)

    log_data = {}
    for date in all_dates:
        # --- FIX: Moved substitution query inside the date loop ---
        subs = DailySubstitution.objects.filter(date=date).select_related('substituted_by')
        sub_map = {s.timetable_id: s.substituted_by for s in subs}

        # Get all conducted and cancelled classes for this specific date
        conducted_entries = Timetable.objects.filter(attendance_records__date=date).distinct()
        cancelled_entries = Timetable.objects.filter(cancellations__date=date).distinct()

        daily_log = []
        for entry in conducted_entries:
            present_count = AttendanceRecord.objects.filter(
                timetable=entry, date=date, status='Present'
            ).count()
            total_students = Profile.objects.filter(student_group=entry.student_group).count()
            was_edited = AttendanceRecord.objects.filter(
                timetable=entry,
                date=date
            ).annotate(
                # Check if updated_at is more than 5 seconds after created_at
                is_edited=ExpressionWrapper(Q(updated_at__gt=F('created_at') + timezone.timedelta(seconds=5)),
                                            output_field=fields.BooleanField())
            ).filter(is_edited=True).exists()

            # --- FIX: Added substitution info to the context for the template ---
            daily_log.append({
                'timetable': entry,
                'status': 'Conducted',
                'present_count': present_count,
                'total_students': total_students,
                'date': date,
                'substituted_by': sub_map.get(entry.id),  # Will be None if no sub exists
                'was_edited': was_edited,
            })

        for entry in cancelled_entries:
            daily_log.append({
                'timetable': entry,
                'status': 'Cancelled',
                'date': date
            })

        daily_log.sort(key=lambda x: x['timetable'].time_slot.start_time)
        log_data[date] = daily_log

    context = {'log_data': log_data}
    return render(request, 'academics/daily_attendance_log.html', context)


@login_required
@permission_required('academics.view_attendancelog', raise_exception=True)
def daily_log_detail_view(request, timetable_id, date):
    """
    Shows the detailed attendance list for a single class session.
    """
    try:
        timetable_entry = Timetable.objects.select_related(
            'subject__subject', 'student_group', 'faculty'
        ).get(pk=timetable_id)

        records = AttendanceRecord.objects.filter(
            timetable=timetable_entry,
            date=date
        ).select_related('student').order_by('student__first_name')

    except ObjectDoesNotExist:
        raise Http404("The requested attendance session does not exist.")

    context = {
        'timetable_entry': timetable_entry,
        'date': date,
        'records': records
    }
    return render(request, 'academics/daily_log_detail.html', context)


@login_required
@permission_required('academics.add_timetable', raise_exception=True)
def timetable_entry_create_view(request, group_id, day, timeslot_id):
    student_group = get_object_or_404(StudentGroup, pk=group_id)
    time_slot = get_object_or_404(TimeSlot, pk=timeslot_id)

    if request.method == 'POST':
        form = TimetableEntryForm(request.POST, student_group=student_group)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.student_group = student_group
            entry.day_of_week = day
            entry.time_slot = time_slot
            entry.save()
            return JsonResponse({'success': True, 'message': 'Period added successfully.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})

    form = TimetableEntryForm(student_group=student_group)
    context = {'form': form, 'form_title': f"Add Period for {day} at {time_slot}"}
    return render(request, 'partials/modal_form.html', context)


@login_required
@permission_required('academics.change_timetable', raise_exception=True)
def timetable_entry_update_view(request, entry_id):
    entry = get_object_or_404(Timetable, pk=entry_id)
    student_group = entry.student_group

    if request.method == 'POST':
        form = TimetableEntryForm(request.POST, instance=entry, student_group=student_group)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Period updated successfully.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})

    form = TimetableEntryForm(instance=entry, student_group=student_group)
    context = {'form': form, 'form_title': f"Edit Period"}
    return render(request, 'partials/modal_form.html', context)


@login_required
@permission_required('academics.delete_timetable', raise_exception=True)
def timetable_entry_delete_view(request, entry_id):
    entry = get_object_or_404(Timetable, pk=entry_id)
    if request.method == 'POST':
        entry.delete()
        return JsonResponse({'success': True, 'message': 'Period deleted successfully.'})
    return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)


@login_required
@permission_required('academics.view_timetable', raise_exception=True)
@nav_item(title="Manage Timetable", icon="iconsminds-calendar-4", url_name="academics:manage_timetable",
          permission='academics.view_timetable', group='admin_management', order=40)
def manage_timetable_view(request):
    student_groups = StudentGroup.objects.all()
    selected_group = None
    timetable_grid = {}

    group_id = request.GET.get('group_id')
    if group_id:
        selected_group = get_object_or_404(StudentGroup, pk=group_id)

        entries = Timetable.objects.filter(student_group=selected_group).select_related('subject__subject', 'faculty',
                                                                                        'time_slot')

        for entry in entries:
            if entry.day_of_week not in timetable_grid:
                timetable_grid[entry.day_of_week] = {}
            timetable_grid[entry.day_of_week][entry.time_slot.id] = entry

    context = {
        'student_groups': student_groups,
        'selected_group': selected_group,
        'timeslots': TimeSlot.objects.all(),
        'days_of_week': [day[0] for day in Timetable.DAY_CHOICES],
        'timetable_grid': timetable_grid,
    }
    return render(request, 'academics/manage_timetable.html', context)


@login_required
@permission_required('academics.add_dailysubstitution', raise_exception=True)
@nav_item(title="Manage Substitutions", icon="iconsminds-shuffle-1", url_name="academics:manage_substitutions",
          group='admin_management', permission='academics.add_dailysubstitution', order=50)
def manage_substitutions_view(request):
    # Get the date from the request's GET parameters, default to today if not provided
    selected_date_str = request.GET.get('date', timezone.now().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    day_of_week = selected_date.strftime('%A')

    # Get the schedule and existing substitutions for the selected date
    todays_schedule = Timetable.objects.filter(day_of_week=day_of_week).order_by('time_slot')
    existing_substitutions = DailySubstitution.objects.filter(date=selected_date).select_related('substituted_by')

    # Create a dictionary for easy lookup in the template
    substitutions_map = {sub.timetable_id: sub.substituted_by for sub in existing_substitutions}

    context = {
        'selected_date': selected_date,
        'schedule': todays_schedule,
        'substitutions_map': substitutions_map,
        'substitution_form': SubstitutionForm()  # An instance of our new form
    }
    return render(request, 'academics/manage_substitutions.html', context)


@login_required
@permission_required('academics.add_dailysubstitution', raise_exception=True)
def assign_substitution_view(request, timetable_id):
    if request.method == 'POST':
        form = SubstitutionForm(request.POST)
        if form.is_valid():
            timetable_entry = get_object_or_404(Timetable, pk=timetable_id)
            substitute_faculty = form.cleaned_data['substitute_faculty']
            date = request.POST.get('date')  # Get the date from the POST data

            # Use update_or_create to handle both new and existing substitutions
            DailySubstitution.objects.update_or_create(
                timetable=timetable_entry,
                date=date,
                defaults={'substituted_by': substitute_faculty}
            )
            messages.success(request, f"Substitution saved for {timetable_entry.subject.subject.name}.")
        else:
            messages.error(request, "Invalid selection. Please try again.")

    # Redirect back to the substitution page for the same date
    return redirect(f"{reverse('academics:manage_substitutions')}?date={request.POST.get('date', '')}")


@login_required
@permission_required('academics.delete_dailysubstitution', raise_exception=True)
def cancel_substitution_view(request, timetable_id):
    if request.method == 'POST':
        date_str = request.POST.get('date')
        # Find the specific substitution and delete it
        substitution = get_object_or_404(DailySubstitution, timetable_id=timetable_id, date=date_str)
        substitution.delete()
        messages.success(request, "Substitution has been cancelled successfully.")
        # Redirect back to the same date on the management page
        return redirect(f"{reverse('academics:manage_substitutions')}?date={date_str}")

    # Redirect to the main page if accessed via GET
    return redirect('academics:manage_substitutions')


@login_required
@permission_required('academics.view_own_attendance', raise_exception=True)
@nav_item(title="My Attendance", icon="simple-icon-pie-chart", url_name="academics:student_my_attendance",
          permission='academics.view_own_attendance', group='my_academics', order=1)
def student_my_attendance_view(request):
    """
    Allows a logged-in student to view their own attendance details,
    filtered by semester, with charts for visualization.
    """
    student = request.user
    student_group = student.profile.student_group if hasattr(student, 'profile') else None

    subject_attendance_data = []
    available_semesters = []
    selected_semester = request.GET.get('semester')

    if student_group and student_group.course:
        all_course_subjects_qs = CourseSubject.objects.filter(course=student_group.course)
        available_semesters = all_course_subjects_qs.values_list('semester', flat=True).distinct().order_by('semester')

        # Default to the latest semester if none is selected
        if not selected_semester and available_semesters:
            selected_semester = available_semesters.last()

        subjects_for_semester = all_course_subjects_qs
        if selected_semester and str(selected_semester).isdigit():
            subjects_for_semester = all_course_subjects_qs.filter(semester=selected_semester)

        for course_subject in subjects_for_semester:
            total_classes = AttendanceRecord.objects.filter(
                timetable__student_group=student_group,
                timetable__subject=course_subject
            ).values('date', 'timetable_id').distinct().count()

            student_records = AttendanceRecord.objects.filter(
                student=student,
                timetable__subject=course_subject
            )
            present_count = student_records.filter(status='Present').count()

            absent_count = total_classes - present_count
            official_percentage = (present_count / total_classes * 100) if total_classes > 0 else 0

            subject_attendance_data.append({
                'subject_pk': course_subject.subject.pk,
                'subject_name': course_subject.subject.name,
                'attended_classes': present_count,
                'absent_classes': absent_count if absent_count >= 0 else 0,
                'on_duty_classes': 0,
                'total_classes': total_classes,
                'official_percentage': round(official_percentage, 2),
            })

    # Calculate Overall data
    overall_attended = sum(item['attended_classes'] for item in subject_attendance_data)
    overall_absent = sum(item['absent_classes'] for item in subject_attendance_data)
    overall_on_duty = 0
    overall_official_percentage = ((overall_attended / (overall_attended + overall_absent)) * 100) if (
                                                                                                              overall_attended + overall_absent) > 0 else 0

    context = {
        'student': student,
        'student_group': student_group,
        'subject_attendance_data': subject_attendance_data,
        'subject_attendance_data_json': json.dumps(subject_attendance_data),
        'available_semesters': available_semesters,
        'selected_semester': int(selected_semester) if selected_semester and str(selected_semester).isdigit() else None,
        'overall_attended': overall_attended,
        'overall_absent': overall_absent,
        'overall_on_duty': overall_on_duty,
        'overall_official_percentage': round(overall_official_percentage, 2)
    }
    return render(request, 'academics/student_my_attendance.html', context)


@login_required
@permission_required('academics.change_attendancerecord', raise_exception=True)
@nav_item(title="Edit Past Attendance", icon="simple-icon-note", url_name="academics:previous_attendance",
          permission='academics.change_attendancerecord', group='faculty_tools', order=20)
def previous_attendance_view(request):
    settings = AttendanceSettings.load()
    # Calculate the cutoff date based on the edit deadline
    cutoff_date = timezone.now().date() - timezone.timedelta(days=settings.edit_deadline_days)

    # Find all distinct sessions marked by this faculty within the deadline
    marked_sessions = AttendanceRecord.objects.filter(
        marked_by=request.user,
        date__gte=cutoff_date
    ).values('date', 'timetable_id').distinct().order_by('-date')

    # Fetch the related timetable details for display
    session_details = []
    for session in marked_sessions:
        entry = Timetable.objects.select_related('time_slot', 'subject__subject', 'student_group').get(
            pk=session['timetable_id'])
        session_details.append({
            'date': session['date'],
            'timetable': entry
        })

    context = {'sessions': session_details}
    return render(request, 'academics/previous_attendance.html', context)


@login_required
@permission_required('academics.view_own_timetable', raise_exception=True)  # Re-using existing student permission
@nav_item(title="My Timetable", icon="iconsminds-calendar-4", url_name="academics:student_timetable",
          permission='academics.view_own_timetable', group='my_academics', order=2)
def student_timetable_view(request):
    """
    Displays the weekly timetable for the logged-in student's class.
    """
    student_group = request.user.profile.student_group
    timetable_grid = {}

    if student_group:
        entries = Timetable.objects.filter(student_group=student_group).select_related(
            'subject__subject', 'faculty', 'time_slot'
        )
        for entry in entries:
            if entry.day_of_week not in timetable_grid:
                timetable_grid[entry.day_of_week] = {}
            timetable_grid[entry.day_of_week][entry.time_slot.id] = entry

    context = {
        'student_group': student_group,
        'timeslots': TimeSlot.objects.filter(is_schedulable=True),
        'days_of_week': [day[0] for day in Timetable.DAY_CHOICES],
        'timetable_grid': timetable_grid,
    }
    return render(request, 'academics/student_timetable.html', context)


@login_required
@permission_required('academics.view_attendancerecord')  # Admin permission
@nav_item(title="Attendance Reports", icon="simple-icon-printer", url_name="academics:attendance_report",
          permission='academics.view_attendancerecord', group='admin_management')
def attendance_report_view(request):
    form = AttendanceReportForm()
    return render(request, 'academics/attendance_report_form.html', {'form': form})


@login_required
@permission_required('academics.view_attendancerecord')
def download_attendance_report_view(request):
    group_id = request.GET.get('student_group')
    subject_id = request.GET.get('subject')
    month = int(request.GET.get('month'))
    year = int(request.GET.get('year'))

    student_group = StudentGroup.objects.get(pk=group_id)
    subject = Subject.objects.get(pk=subject_id)
    students = User.objects.filter(profile__student_group=student_group).order_by('last_name', 'first_name')

    # Fetch all attendance records for the specific subject, class, and month
    records = AttendanceRecord.objects.filter(
        timetable__student_group=student_group,
        timetable__subject__subject=subject,
        date__year=year,
        date__month=month
    ).order_by('date')  # Order by date to process chronologically

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"{subject.name} - {student_group.name}"

    # Create Header Row for ALL days in the month
    num_days = calendar.monthrange(year, month)[1]
    headers = ["Student Name"] + list(range(1, num_days + 1))
    sheet.append(headers)
    for col in sheet.iter_cols(min_row=1, max_row=1, min_col=1, max_col=len(headers)):
        for cell in col:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

    # --- FIX: Manually ensure uniqueness in Python instead of the DB ---
    records_dict = {}
    processed_keys = set()  # Keep track of (student_id, day) pairs we've already handled
    for record in records:
        key = (record.student.id, record.date.day)
        if key not in processed_keys:
            records_dict[key] = record.status[0]
            processed_keys.add(key)
    # --- END FIX ---

    # Populate Data Rows
    for student in students:
        row_data = [student.get_full_name()]
        for day in range(1, num_days + 1):
            status = records_dict.get((student.id, day), "-")
            row_data.append(status)
        sheet.append(row_data)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response[
        'Content-Disposition'] = f'attachment; filename="Attendance_{subject.name}_{student_group.name}_{month}_{year}.xlsx"'
    workbook.save(response)

    return response


@login_required
@permission_required('academics.can_send_announcement')
@nav_item(title="Announcements", icon="simple-icon-speech", url_name="academics:announcement_list",
          permission='academics.can_send_announcement', group='admin_management')
def announcement_list_view(request):
    announcements = Announcement.objects.all()
    return render(request, 'academics/announcement_list.html', {'announcements': announcements})


@login_required
@permission_required('academics.can_send_announcement')
@transaction.atomic
def announcement_create_view(request):
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            # Create the object in memory but don't save to DB yet
            announcement = form.save(commit=False)
            announcement.sender = request.user

            # Now save the main object and its M2M relationships.
            # The transaction ensures this is an all-or-nothing operation.
            announcement.save()
            form.save_m2m()

            messages.success(request, "Announcement has been sent successfully.")
            return redirect('academics:announcement_list')
    else:
        form = AnnouncementForm()
    return render(request, 'academics/announcement_form.html', {'form': form})


@login_required
def check_announcements_view(request):
    """
    Checks for the single latest unread announcement for the user.
    If found, returns its data and marks it as seen to prevent future pop-ups.
    """
    user = request.user

    # Admins don't get pop-ups
    if not hasattr(user, 'profile') or user.profile.role == 'admin':
        return JsonResponse({'announcement': None})

    # Determine which announcements are relevant to this user
    target_filter = Q()
    if user.profile.role == 'student' and user.profile.student_group:
        target_filter = Q(send_to_all_students=True) | Q(target_student_groups=user.profile.student_group)
    elif user.profile.role == 'faculty':
        target_filter = Q(send_to_all_faculty=True)

    if not target_filter:
        return JsonResponse({'announcement': None})

    # Find the latest announcement that the user has NOT seen yet
    try:
        latest_unread = Announcement.objects.filter(target_filter).exclude(
            usernotificationstatus__user=user
        ).latest('created_at')  # .latest() gets the single newest one

        # Mark this announcement as seen immediately so it doesn't pop up again
        UserNotificationStatus.objects.create(user=user, announcement=latest_unread)

        # Prepare the data to send to the frontend
        announcement_data = {
            'title': latest_unread.title,
            'content': latest_unread.content,
            'timestamp': latest_unread.created_at.strftime('%b %d, %Y, %I:%M %p'),
        }
        return JsonResponse({'announcement': announcement_data})

    except Announcement.DoesNotExist:
        # No unread announcements found, which is a normal case
        return JsonResponse({'announcement': None})


@login_required
def global_search_view(request):
    """
    Handles the global search query from the top navigation bar.
    Searches for Students, Faculty, and Subjects.
    """
    query = request.GET.get('q', '')
    students_found = User.objects.none()
    faculty_found = User.objects.none()
    subjects_found = Subject.objects.none()

    if query:
        # Search for students by name, username, or student ID
        students_found = User.objects.filter(
            Q(profile__role='student') &
            (Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query) | Q(
                profile__student_id_number__icontains=query))
        ).distinct()

        # Search for faculty by name or username
        faculty_found = User.objects.filter(
            Q(profile__role='faculty') &
            (Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query))
        ).distinct()

        # Search for subjects by name or code
        subjects_found = Subject.objects.filter(
            Q(name__icontains=query) | Q(code__icontains=query)
        )

    context = {
        'query': query,
        'students': students_found,
        'faculty': faculty_found,
        'subjects': subjects_found,
        'result_count': len(students_found) + len(faculty_found) + len(subjects_found)
    }
    return render(request, 'academics/search_results.html', context)


@login_required
@permission_required('academics.view_attendancerecord', raise_exception=True)
@nav_item(title="Late Comers", icon="simple-icon-clock", url_name="academics:late_comers",
          permission='academics.view_attendancerecord', group='admin_management', order=60)
def late_comers_view(request):
    student_groups = StudentGroup.objects.all()
    selected_group_id = request.GET.get('student_group')
    selected_month = request.GET.get('month', str(timezone.now().month))
    selected_year = request.GET.get('year', str(timezone.now().year))

    late_comers_data = []
    if selected_group_id:
        student_group = get_object_or_404(StudentGroup, pk=selected_group_id)
        late_records = AttendanceRecord.objects.filter(
            timetable__student_group=student_group,
            is_late=True,  # This is the correct filter
            date__month=selected_month,
            date__year=selected_year
        ).values('student__id', 'student__first_name', 'student__last_name').annotate(late_count=Count('student'))

        for record in late_records:
            late_comers_data.append({
                'student_name': f"{record['student__first_name']} {record['student__last_name']}",
                'late_count': record['late_count']
            })

    context = {
        'student_groups': student_groups,
        'selected_group_id': int(selected_group_id) if selected_group_id else None,
        'selected_month': int(selected_month),
        'selected_year': int(selected_year),
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(timezone.now().year, timezone.now().year - 5, -1),
        'late_comers_data': late_comers_data
    }
    return render(request, 'academics/late_comers.html', context)


@login_required
@permission_required('auth.view_user')
def student_profile_view(request, student_id):
    student = get_object_or_404(User, pk=student_id, profile__role='student')

    # --- Initialize all context variables ---
    overall_attendance, total_subjects, current_semester = 0, 0, None
    overall_marks_percentage = 0
    marks_summary = {}

    student_group = student.profile.student_group
    if student_group:
        latest_semester_instance = CourseSubject.objects.filter(
            course=student_group.course
        ).order_by('-semester').first()

        if latest_semester_instance:
            current_semester = latest_semester_instance.semester
            subjects_for_semester = CourseSubject.objects.filter(
                course=student_group.course, semester=current_semester
            )
            total_subjects = subjects_for_semester.count()

            # --- Attendance Calculation ---
            total_classes = AttendanceRecord.objects.filter(
                timetable__student_group=student_group,
                timetable__subject__in=subjects_for_semester
            ).values('date', 'timetable__time_slot').distinct().count()
            present_count = AttendanceRecord.objects.filter(
                student=student,
                timetable__subject__in=subjects_for_semester,
                status__in=['Present', 'Late']
            ).count()
            if total_classes > 0:
                overall_attendance = round((present_count / total_classes) * 100, 1)

            # --- Marks Calculation ---
            marks_qs = Mark.objects.filter(student=student, subject__in=subjects_for_semester)
            total_marks_obtained = marks_qs.aggregate(total=Sum('marks_obtained'))['total'] or 0
            total_max_marks = marks_qs.aggregate(total=Sum('criterion__max_marks'))['total'] or 0
            if total_max_marks > 0:
                overall_marks_percentage = round((total_marks_obtained / total_max_marks) * 100, 1)

            # --- Structure Marks Data for the Template ---
            for mark in marks_qs.select_related('subject__subject', 'criterion').order_by('subject__subject__name'):
                subject_name = mark.subject.subject.name
                if subject_name not in marks_summary:
                    marks_summary[subject_name] = {'criteria': [], 'total_obtained': 0, 'total_max': 0}

                marks_summary[subject_name]['criteria'].append({
                    'name': mark.criterion.name, 'marks': mark.marks_obtained, 'max': mark.criterion.max_marks
                })
                marks_summary[subject_name]['total_obtained'] += mark.marks_obtained
                marks_summary[subject_name]['total_max'] += mark.criterion.max_marks

    context = {
        'student': student, 'overall_attendance': overall_attendance, 'total_subjects': total_subjects,
        'current_semester': current_semester, 'overall_marks_percentage': overall_marks_percentage,
        'marks_summary': marks_summary
    }
    return render(request, 'academics/student_profile.html', context)


@login_required
@permission_required('academics.view_markingscheme')
@nav_item(title="Marking Schemes", icon="iconsminds-testimonal", url_name="academics:scheme_list",
          permission='academics.view_markingscheme', group='admin_management', order=50)
def scheme_list_view(request):
    schemes = MarkingScheme.objects.all()
    return render(request, 'academics/scheme_list.html', {'schemes': schemes})


@login_required
@permission_required('academics.add_markingscheme')
def scheme_create_view(request):
    if request.method == 'POST':
        form = MarkingSchemeForm(request.POST)
        formset = CriterionFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            scheme = form.save()
            formset.instance = scheme
            formset.save()
            messages.success(request, 'Marking scheme created successfully.')
            return redirect('academics:scheme_list')
    else:
        form = MarkingSchemeForm()
        formset = CriterionFormSet()

    context = {
        'form': form,
        'formset': formset,
        'form_title': 'Create New Marking Scheme'
    }
    return render(request, 'academics/scheme_form.html', context)


@login_required
@permission_required('academics.change_markingscheme')
def scheme_update_view(request, pk):
    scheme = get_object_or_404(MarkingScheme, pk=pk)
    if request.method == 'POST':
        form = MarkingSchemeForm(request.POST, instance=scheme)
        formset = CriterionFormSet(request.POST, instance=scheme)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Marking scheme updated successfully.')
            return redirect('academics:scheme_list')
    else:
        form = MarkingSchemeForm(instance=scheme)
        formset = CriterionFormSet(instance=scheme)

    context = {
        'form': form,
        'formset': formset,
        'form_title': f'Edit Marking Scheme: {scheme.name}'
    }
    return render(request, 'academics/scheme_form.html', context)


@login_required
@permission_required('academics.delete_markingscheme')
def scheme_delete_view(request, pk):
    scheme = get_object_or_404(MarkingScheme, pk=pk)
    if request.method == 'POST':
        scheme.delete()
        messages.success(request, 'Marking scheme has been deleted.')
        return redirect('academics:scheme_list')
    return render(request, 'academics/confirm_delete.html', {'item': scheme, 'type': 'Marking Scheme'})


@login_required
@permission_required('academics.add_mark')
@nav_item(title="Enter Marks", icon="simple-icon-note", url_name="academics:marks_entry",
          permission='academics.add_mark', group='faculty_tools', order=30)
def marks_entry_view(request):
    # Get all unique classes the faculty teaches
    taught_entries = Timetable.objects.filter(faculty=request.user).select_related('student_group',
                                                                                   'subject__subject').distinct()
    group_ids = taught_entries.values_list('student_group_id', flat=True).distinct()
    groups_queryset = StudentGroup.objects.filter(id__in=group_ids)

    # Initialize the form with an empty subjects queryset, as it will be populated dynamically
    subjects_queryset = CourseSubject.objects.none()
    form = MarkSelectForm(request.GET or None, groups_queryset=groups_queryset, subjects_queryset=subjects_queryset)

    # --- MODIFICATION STARTS HERE ---
    # Create a map of groups to their current semester's subjects for the dynamic dropdown
    group_subject_map = {}
    # Eager load the course to avoid extra queries inside the loop
    for group in groups_queryset.select_related('course'):
        # Find the latest (current) semester for the group's course
        latest_semester_num = CourseSubject.objects.filter(
            course=group.course
        ).order_by('-semester').values_list('semester', flat=True).first()

        # If no semester is defined for the course, there are no subjects to show
        if not latest_semester_num:
            group_subject_map[group.id] = []
            continue

        # Get all subject IDs the faculty teaches for this specific group
        subject_ids = taught_entries.filter(
            student_group=group
        ).values_list('subject_id', flat=True).distinct()

        # Filter the subjects to only include those from the current semester
        current_semester_subjects = CourseSubject.objects.filter(
            id__in=subject_ids,
            semester=latest_semester_num
        ).select_related('subject')

        # Build the map for the dependent dropdown
        group_subject_map[group.id] = [
            {'id': s.id, 'name': s.subject.name} for s in current_semester_subjects
        ]
    # --- MODIFICATION ENDS HERE ---

    students, criteria, existing_marks = None, None, {}
    student_group_id = request.GET.get('student_group')
    course_subject_id = request.GET.get('course_subject')

    if student_group_id and course_subject_id:
        students = User.objects.filter(profile__student_group_id=student_group_id, profile__role='student').order_by(
            'first_name')
        course_subject = get_object_or_404(CourseSubject, pk=course_subject_id)
        active_scheme = course_subject.course.marking_scheme

        if active_scheme:
            criteria = active_scheme.criteria.all()
            marks_qs = Mark.objects.filter(
                student__in=students,
                subject=course_subject,
                criterion__in=criteria
            )
            # Create a nested dictionary for easy lookup in the template
            for mark in marks_qs:
                if mark.student_id not in existing_marks:
                    existing_marks[mark.student_id] = {}
                existing_marks[mark.student_id][mark.criterion_id] = mark.marks_obtained

    if request.method == 'POST':
        subject = get_object_or_404(CourseSubject, pk=course_subject_id)
        active_scheme = subject.course.marking_scheme
        if active_scheme and students:
            for student in students:
                for criterion in active_scheme.criteria.all():
                    input_name = f'marks-{student.id}-{criterion.id}'
                    marks_val = request.POST.get(input_name)
                    if marks_val:
                        Mark.objects.update_or_create(
                            student=student, subject=subject, criterion=criterion,
                            defaults={'marks_obtained': marks_val}
                        )
            messages.success(request, "Marks have been saved successfully.")
            return redirect(request.get_full_path())

    context = {
        'form': form,
        'students': students,
        'criteria': criteria,
        'existing_marks': existing_marks,
        'selected_group': student_group_id,
        'selected_subject': course_subject_id,
        'group_subject_map_json': json.dumps(group_subject_map)
    }
    return render(request, 'academics/marks_entry_form.html', context)


@login_required
@permission_required('academics.add_mark')
def download_marks_template_view(request):
    """
    Generates and serves a blank CSV template for bulk marks import.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="marks_import_template.csv"'

    writer = csv.writer(response)
    # These are the required headers for the import to work
    writer.writerow(['student_username', 'subject_code', 'criterion_name', 'marks_obtained'])

    return response


@login_required
@permission_required('academics.add_mark')
@nav_item(title="Bulk Import Marks", icon="iconsminds-up", url_name="academics:bulk_marks_import",
          permission='academics.add_mark', group='faculty_tools')
def bulk_marks_import_view(request):
    if request.method == 'POST':
        form = BulkMarksImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)

            success_count = 0
            error_list = []

            try:
                with transaction.atomic():
                    for row_num, row in enumerate(reader, 2):
                        username = row.get('student_username')
                        subject_code = row.get('subject_code')
                        criterion_name = row.get('criterion_name')
                        marks = row.get('marks_obtained')

                        try:
                            student = User.objects.get(username=username)
                            subject = CourseSubject.objects.get(subject__code=subject_code)
                            criterion = Criterion.objects.get(name=criterion_name)

                            Mark.objects.update_or_create(
                                student=student,
                                subject=subject,
                                criterion=criterion,
                                defaults={'marks_obtained': marks}
                            )
                            success_count += 1

                        except User.DoesNotExist:
                            error_list.append(f"Row {row_num}: Student '{username}' not found.")
                        except CourseSubject.DoesNotExist:
                            error_list.append(f"Row {row_num}: Subject with code '{subject_code}' not found.")
                        except Criterion.DoesNotExist:
                            error_list.append(f"Row {row_num}: Criterion '{criterion_name}' not found.")
                        except Exception as e:
                            error_list.append(f"Row {row_num}: An unexpected error occurred - {e}")

                    if error_list:
                        raise Exception("Import failed, rolling back transaction.")

            except Exception as e:
                messages.error(request, str(e))

            if not error_list:
                messages.success(request, f"Successfully imported marks for {success_count} records.")
            else:
                messages.warning(request,
                                 f"Import completed with errors. Successfully imported: {success_count}. Failed: {len(error_list)}.")

            return render(request, 'academics/bulk_marks_import.html',
                          {'form': BulkMarksImportForm(), 'errors': error_list})
    else:
        form = BulkMarksImportForm()

    return render(request, 'academics/bulk_marks_import.html', {'form': form})


@login_required
@permission_required('academics.view_own_marks')  # Assuming this permission
@nav_item(title="My Marks", icon="simple-icon-graduation", url_name="academics:student_my_marks",
          permission='academics.view_own_marks', group='my_academics', order=3)
def student_my_marks_view(request):
    student = request.user

    # Get available semesters for the student's course
    available_semesters = []
    if student.profile.student_group:
        available_semesters = CourseSubject.objects.filter(
            course=student.profile.student_group.course
        ).values_list('semester', flat=True).distinct().order_by('semester')

    # Get the selected semester from the request, or default to the latest one
    selected_semester = request.GET.get('semester')
    if not selected_semester and available_semesters:
        selected_semester = available_semesters.last()

    marks_data = {}
    if selected_semester:
        selected_semester = int(selected_semester)
        # Fetch all marks for the student in the selected semester
        marks_qs = Mark.objects.filter(
            student=student,
            subject__semester=selected_semester
        ).select_related('subject__subject', 'criterion')

        # Process the marks into a dictionary grouped by subject
        for mark in marks_qs:
            subject_name = mark.subject.subject.name
            if subject_name not in marks_data:
                marks_data[subject_name] = {
                    'criteria': [],
                    'total_marks': 0,
                    'max_total': 0
                }

            marks_data[subject_name]['criteria'].append({
                'name': mark.criterion.name,
                'marks_obtained': mark.marks_obtained,
                'max_marks': mark.criterion.max_marks
            })
            marks_data[subject_name]['total_marks'] += mark.marks_obtained
            marks_data[subject_name]['max_total'] += mark.criterion.max_marks

    context = {
        'marks_data': marks_data,
        'available_semesters': available_semesters,
        'selected_semester': selected_semester,
    }
    return render(request, 'academics/student_my_marks.html', context)


@login_required
@permission_required('academics.view_mark')
@nav_item(title="Marks Reports", icon="simple-icon-printer", url_name="academics:marks_report",
          permission='academics.view_mark', group='admin_management')
def marks_report_view(request):
    """
    Displays a form to select criteria for the marks report.
    """
    form = MarksReportForm()
    return render(request, 'academics/marks_report_form.html', {'form': form})


@login_required
@permission_required('academics.view_mark')
def download_marks_report_view(request):
    """
    Generates and serves an Excel file containing the marks for the selected class and semester.
    """
    group_id = request.GET.get('student_group')
    semester = request.GET.get('semester')

    if not group_id or not semester:
        return HttpResponse("Please select a class and semester.", status=400)

    student_group = get_object_or_404(StudentGroup, pk=group_id)
    students = User.objects.filter(profile__student_group=student_group).order_by('first_name')
    course_subjects = CourseSubject.objects.filter(
        course=student_group.course,
        semester=semester
    ).select_related('subject')

    # Create an in-memory workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f"Sem {semester} Marks - {student_group.name}"

    # --- Create Header Row ---
    headers = ["Student Name", "Student ID"] + [cs.subject.name for cs in course_subjects]
    sheet.append(headers)
    for cell in sheet[1]:  # Style the header row
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    # --- Prepare data ---
    # Get all marks for the selected students and subjects in one query
    all_marks = Mark.objects.filter(
        student__in=students,
        subject__in=course_subjects
    ).values(
        'student_id', 'subject_id'
    ).annotate(
        total_marks=Sum('marks_obtained')
    )

    # Pivot the data for easy lookup
    marks_pivot = {}
    for mark in all_marks:
        if mark['student_id'] not in marks_pivot:
            marks_pivot[mark['student_id']] = {}
        marks_pivot[mark['student_id']][mark['subject_id']] = mark['total_marks']

    # --- Populate Data Rows ---
    for student in students:
        row_data = [student.get_full_name(), student.profile.student_id_number]
        student_marks = marks_pivot.get(student.id, {})
        for cs in course_subjects:
            marks = student_marks.get(cs.id, 0)  # Default to 0 if no mark found
            row_data.append(marks)
        sheet.append(row_data)

    # --- Prepare the response ---
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Marks_{student_group.name}_Sem_{semester}.xlsx"'
    workbook.save(response)

    return response


@login_required
@permission_required('accounts.view_own_profile')  # Assuming a base permission
@nav_item(title="My Profile", icon="simple-icon-user", url_name="academics:my_profile",
          permission='accounts.view_own_profile', group='my_academics', order=0)
def my_profile_view(request):
    """
    Displays the profile page for the currently logged-in user.
    """
    student = request.user

    # --- FIX STARTS HERE: Added full logic to fetch profile data ---
    overall_attendance, total_subjects, current_semester = 0, 0, None
    overall_marks_percentage = 0
    marks_summary = {}

    # Ensure the user is a student with a profile before calculating
    if hasattr(student, 'profile') and student.profile.role == 'student':
        student_group = student.profile.student_group
        if student_group:
            latest_semester_instance = CourseSubject.objects.filter(
                course=student_group.course
            ).order_by('-semester').first()

            if latest_semester_instance:
                current_semester = latest_semester_instance.semester
                subjects_for_semester = CourseSubject.objects.filter(
                    course=student_group.course, semester=current_semester
                )
                total_subjects = subjects_for_semester.count()

                # --- Attendance Calculation ---
                total_classes = AttendanceRecord.objects.filter(
                    timetable__student_group=student_group,
                    timetable__subject__in=subjects_for_semester
                ).values('date', 'timetable__time_slot').distinct().count()
                present_count = AttendanceRecord.objects.filter(
                    student=student,
                    timetable__subject__in=subjects_for_semester,
                    status__in=['Present', 'Late']
                ).count()
                if total_classes > 0:
                    overall_attendance = round((present_count / total_classes) * 100, 1)

                # --- Marks Calculation ---
                marks_qs = Mark.objects.filter(student=student, subject__in=subjects_for_semester)
                total_marks_obtained = marks_qs.aggregate(total=Sum('marks_obtained'))['total'] or 0
                total_max_marks = marks_qs.aggregate(total=Sum('criterion__max_marks'))['total'] or 0
                if total_max_marks > 0:
                    overall_marks_percentage = round((total_marks_obtained / total_max_marks) * 100, 1)

                # --- Structure Marks Data for the Template ---
                for mark in marks_qs.select_related('subject__subject', 'criterion').order_by('subject__subject__name'):
                    subject_name = mark.subject.subject.name
                    if subject_name not in marks_summary:
                        marks_summary[subject_name] = {'criteria': [], 'total_obtained': 0, 'total_max': 0}

                    marks_summary[subject_name]['criteria'].append({
                        'name': mark.criterion.name, 'marks': mark.marks_obtained, 'max': mark.criterion.max_marks
                    })
                    marks_summary[subject_name]['total_obtained'] += mark.marks_obtained
                    marks_summary[subject_name]['total_max'] += mark.criterion.max_marks

    context = {
        'student': student,
        'overall_attendance': overall_attendance,
        'total_subjects': total_subjects,
        'current_semester': current_semester,
        'overall_marks_percentage': overall_marks_percentage,
        'marks_summary': marks_summary
    }
    # --- FIX ENDS HERE ---

    # We can reuse the same template as the admin-facing profile view
    return render(request, 'academics/student_profile.html', context)


@login_required
@permission_required('academics.add_extraclass')
@nav_item(title="Schedule Extra Class", icon="simple-icon-plus", url_name="academics:schedule_extra_class",
          permission='academics.add_extraclass', group='faculty_tools', order=40)
def schedule_extra_class(request):
    if request.method == 'POST':
        form = ExtraClassForm(request.POST, user=request.user)
        if form.is_valid():
            # ... (your existing POST logic is correct and remains here) ...
            with transaction.atomic():
                extra_class = form.save(commit=False)
                if request.user.profile.role == 'faculty':
                    extra_class.teacher = request.user
                extra_class.save()

                announcement = Announcement.objects.create(
                    title=f"Extra Class: {extra_class.subject.subject.name}",
                    content=f"An extra class for {extra_class.subject.subject.name} has been scheduled on {extra_class.date} during the {extra_class.time_slot} slot.",
                    sender=request.user
                )
                announcement.target_student_groups.add(extra_class.class_group)
                extra_class.announcement = announcement
                extra_class.save()

            messages.success(request, 'Extra class scheduled successfully and announcement created.')
            return redirect('academics:extra_class_list')
        else:
            messages.warning(request, "Please complete all required fields.")
    else:
        # --- FIX: Handle GET requests for filtering ---
        initial_data = {}
        # If a teacher was selected via the dropdown reload, pass it to the form
        if 'teacher' in request.GET:
            initial_data['teacher'] = request.GET.get('teacher')

        form = ExtraClassForm(user=request.user, initial=initial_data)
        # --- END FIX ---

    context = {
        'form': form,
        'form_title': 'Schedule an Extra Class'
    }
    return render(request, 'academics/extra_class_form.html', context)


@login_required
@permission_required('academics.update_extraclass')
def extra_class_update(request, pk):
    extra_class = get_object_or_404(ExtraClass, pk=pk)
    if request.method == 'POST':
        form = ExtraClassForm(request.POST, instance=extra_class, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Extra class updated successfully.')
            return redirect('academics:extra_class_list')
    else:
        # --- FIX: Handle GET requests for filtering ---
        initial_data = {}
        # If a teacher was selected via the dropdown reload, pass it to the form
        if 'teacher' in request.GET:
            initial_data['teacher'] = request.GET.get('teacher')

        form = ExtraClassForm(instance=extra_class, user=request.user, initial=initial_data)
        # --- END FIX ---

    return render(request, 'academics/extra_class_form.html', {'form': form, 'form_title': f'Edit Extra Class'})

@login_required
@permission_required('academics.view_extraclass')
@nav_item(title="Extra Class", icon="simple-icon-clock", url_name="academics:extra_class_list",
          permission='accounts.view_extraclass', group='admin_management', order=0)
def extra_class_list(request):
    extra_classes = ExtraClass.objects.all()
    return render(request, 'academics/extra_class_list.html', {'extra_classes': extra_classes})


@login_required
@permission_required('academics.delete_extraclass')
def extra_class_delete(request, pk):
    extra_class = get_object_or_404(ExtraClass, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            # --- FIX 1: Use 'sender' instead of 'created_by' ---
            cancellation_announcement = Announcement.objects.create(
                title=f"CANCELLED: Extra Class for {extra_class.subject.name}",
                content=f"The extra class for {extra_class.subject.name} scheduled on {extra_class.date} has been cancelled.",
                sender=request.user
            )
            cancellation_announcement.target_student_groups.add(extra_class.class_group)

            extra_class.delete()

        messages.success(request, 'Extra class deleted and cancellation announcement sent.')
        # --- FIX 3: Use the correct namespaced URL for the redirect ---
        return redirect('academics:extra_class_list')

    # --- FIX 2: Pass the context variables the template expects ---
    context = {
        'item': extra_class,
        'type': 'Extra Class'
    }
    return render(request, 'academics/confirm_delete.html', context)
