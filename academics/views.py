# In academics/views.py
import json
import calendar
from datetime import datetime
from itertools import chain

from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import transaction
from django.db.models import ExpressionWrapper, fields, F, Q
from django.forms import inlineformset_factory, formset_factory
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django import forms
from django.urls import reverse
from django.utils import timezone

from academics.forms import EditStudentForm, AttendanceSettingsForm, TimeSlotForm, MarkAttendanceForm, \
    TimetableEntryForm, SubstitutionForm, AttendanceReportForm, AnnouncementForm
from accounts.models import Profile
from .forms import StudentGroupForm, CourseForm, AddStudentForm, SubjectForm
from .models import StudentGroup, AttendanceSettings, Course, Subject, \
    Timetable, AttendanceRecord, CourseSubject, TimeSlot, ClassCancellation, DailySubstitution, Announcement, \
    UserNotificationStatus
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
            on_duty_count = student_records.filter(status='On Duty').count()

            effective_total = total_classes - on_duty_count
            percentage = (present_count / effective_total * 100) if effective_total > 0 else None

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
@permission_required('academics.view_attendancerecord', raise_exception=True)
def admin_student_attendance_detail_view(request, student_id):
    student = get_object_or_404(User, pk=student_id)
    student_group = student.profile.student_group if hasattr(student, 'profile') else None

    subject_attendance_data = []
    available_semesters = []
    selected_semester = request.GET.get('semester')

    if student_group and student_group.course:
        # ... (semester filtering logic is the same)
        all_course_subjects_qs = CourseSubject.objects.filter(course=student_group.course)
        available_semesters = all_course_subjects_qs.values_list('semester', flat=True).distinct().order_by('semester')

        if selected_semester is None and available_semesters:
            selected_semester = available_semesters.last()

        subjects_for_semester = all_course_subjects_qs
        if selected_semester and str(selected_semester).isdigit():
            subjects_for_semester = all_course_subjects_qs.filter(semester=selected_semester)
        # ...

        for course_subject in subjects_for_semester:
            # --- NEW: Correctly calculate total classes held for the group ---
            total_classes = AttendanceRecord.objects.filter(
                timetable__student_group=student_group,
                timetable__subject=course_subject
            ).values('date', 'timetable_id').distinct().count()

            # --- Now get this specific student's records for that subject ---
            student_records = AttendanceRecord.objects.filter(
                student=student,
                timetable__student_group=student_group,
                timetable__subject=course_subject
            )
            present_count = student_records.filter(status='Present').count()
            on_duty_count = student_records.filter(status='On Duty').count()

            # Calculate absent for visualization (Total - P - OD)
            absent_count = total_classes - (present_count + on_duty_count)

            # Official percentage calculation
            effective_total = total_classes - on_duty_count
            official_percentage = (present_count / effective_total * 100) if effective_total > 0 else 0
            # --- END NEW LOGIC ---

            subject_attendance_data.append({
                'subject_pk': course_subject.subject.pk,
                'subject_name': course_subject.subject.name,
                'attended_classes': present_count,
                'absent_classes': absent_count if absent_count > 0 else 0,
                'on_duty_classes': on_duty_count,
                'official_percentage': round(official_percentage, 2),
            })

    # ... (the rest of the view logic to calculate overall totals is the same) ...

    # Calculate Overall data
    overall_attended = sum(item['attended_classes'] for item in subject_attendance_data)
    overall_absent = sum(item['absent_classes'] for item in subject_attendance_data)
    overall_on_duty = sum(item['on_duty_classes'] for item in subject_attendance_data)
    overall_total = overall_attended + overall_absent + overall_on_duty
    overall_effective_total = overall_total - overall_on_duty
    overall_official_percentage = (
            overall_attended / overall_effective_total * 100) if overall_effective_total > 0 else 0

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
        form = AddStudentForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name']
            )
            # The signal creates the Profile. Now we update it.
            user.profile.role = 'student'
            user.profile.student_id_number = form.cleaned_data['student_id_number']
            user.profile.contact_number = form.cleaned_data['contact_number']

            # --- THIS IS THE FIX ---
            # Assign the student's profile to the current student_group
            user.profile.student_group = student_group

            user.profile.save()

            messages.success(request, f"Student '{user.username}' created and added to {student_group.name}.")
            if '_addanother' in request.POST:
                # Redirect back to the same (empty) create form
                return redirect('academics:student_create', group_id=group_id)
            else:
                return redirect('academics:admin_student_list', group_id=group_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AddStudentForm()

    context = {
        'form': form,
        'form_title': f'Add New Student to {student_group.name}',
        'student_group': student_group
    }
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
    # Get the user and their associated profile
    student_user = get_object_or_404(User, pk=pk, profile__role='student')

    if request.method == 'POST':
        # We pass the 'instance' to pre-fill the Profile part of the form
        form = EditStudentForm(request.POST, instance=student_user.profile)
        if form.is_valid():
            # Save the Profile part of the form
            form.save()
            # Manually update and save the User part
            student_user.first_name = form.cleaned_data['first_name']
            student_user.last_name = form.cleaned_data['last_name']
            student_user.email = form.cleaned_data['email']
            student_user.save()

            messages.success(request, 'Student details updated successfully.')
            student_group = student_user.student_groups.first()
            if student_group:
                return redirect('academics:admin_student_list', group_id=student_group.id)
            else:
                return redirect('home')  # Fallback redirect if student is not in a group
    else:
        # Pre-fill the form with the student's existing data
        form = EditStudentForm(instance=student_user.profile,
                               initial={
                                   'first_name': student_user.first_name,
                                   'last_name': student_user.last_name,
                                   'email': student_user.email
                               })

    context = {
        'form': form,
        'form_title': f'Edit Student: {student_user.get_full_name()}',
        'student_group': student_user.student_groups.first()  # For the cancel button link
    }
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
    settings = AttendanceSettings.load()
    today = timezone.now().date()
    deadline_date = today - timezone.timedelta(days=settings.mark_deadline_days)
    faculty_timetable_slots = Timetable.objects.filter(faculty=request.user)
    day_to_check = deadline_date.strftime('%A')
    slots_to_check = faculty_timetable_slots.filter(day_of_week=day_to_check)
    for slot in slots_to_check:
        # Check if any attendance or cancellation record already exists for this slot on its deadline date
        has_record = AttendanceRecord.objects.filter(timetable=slot, date=deadline_date).exists()
        is_cancelled = ClassCancellation.objects.filter(timetable=slot, date=deadline_date).exists()

        if not has_record and not is_cancelled:
            # If no record exists, automatically mark it as not conducted
            ClassCancellation.objects.create(
                timetable=slot,
                date=deadline_date,
                cancelled_by=None  # Marked by the system
            )
    current_day = timezone.now().strftime('%A')
    current_date = timezone.now().date()
    # 1. Get regularly scheduled classes
    regular_schedule = list(Timetable.objects.filter(
        faculty=request.user, day_of_week=current_day
    ).select_related('time_slot', 'subject__subject', 'student_group'))

    # 2. Get classes this user is substituting for today
    substitutions = DailySubstitution.objects.filter(
        substituted_by=request.user, date=current_date
    ).select_related('timetable__time_slot', 'timetable__subject__subject', 'timetable__student_group')

    # Prepare combined schedule with flags
    schedule_with_status = []

    # Add regular classes
    for entry in regular_schedule:
        entry.is_substitution = False
        schedule_with_status.append(entry)

    # Add substituted classes
    for sub in substitutions:
        entry = sub.timetable
        entry.is_substitution = True
        if entry not in regular_schedule:  # Avoid duplicates if substituting for own class
            schedule_with_status.append(entry)

    # Sort the final combined list by time
    schedule_with_status.sort(key=lambda x: x.time_slot.start_time)

    cancelled_today_ids = ClassCancellation.objects.filter(
        date=current_date
    ).values_list('timetable_id', flat=True)

    context = {
        'schedule': schedule_with_status,
        'current_day': current_day,
        'cancelled_today_ids': cancelled_today_ids
    }
    return render(request, 'academics/faculty_schedule.html', context)


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
                    student = User.objects.get(pk=student_id)

                    # --- THIS IS THE FIX ---
                    # We now use get_or_create to fetch the object first.
                    record, created = AttendanceRecord.objects.get_or_create(
                        student=student,
                        timetable=timetable_entry,
                        date=current_date,
                        defaults={'status': status, 'marked_by': request.user}
                    )

                    # If the record was not new (i.e., it already existed), we are editing it.
                    if not created:
                        record.status = status
                        record.marked_by = request.user
                        # This explicit .save() call is what updates the `updated_at` timestamp.
                        record.save()
                    # --- END FIX ---

            messages.success(request, "Attendance has been marked successfully.")
            return redirect('academics:faculty_schedule')
    else:
        # The GET request logic for pre-filling the form remains the same
        initial_data = []
        existing_records = AttendanceRecord.objects.filter(timetable=timetable_entry, date=current_date)
        status_map = {record.student_id: record.status for record in existing_records}
        for student in students:
            saved_status = status_map.get(student.id)
            initial_data.append({
                'student_id': student.id,
                'status': saved_status if saved_status else 'Present'
            })
        formset = MarkAttendanceFormSet(initial=initial_data)

    student_forms = zip(students, formset)
    context = {
        'timetable_entry': timetable_entry,
        'formset': formset,
        'student_forms': student_forms,
        'date': current_date
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
            on_duty_count = student_records.filter(status='On Duty').count()

            absent_count = total_classes - (present_count + on_duty_count)
            effective_total = total_classes - on_duty_count
            official_percentage = (present_count / effective_total * 100) if effective_total > 0 else 0

            subject_attendance_data.append({
                'subject_pk': course_subject.subject.pk,
                'subject_name': course_subject.subject.name,
                'attended_classes': present_count,
                'absent_classes': absent_count if absent_count >= 0 else 0,
                'on_duty_classes': on_duty_count,
                'total_classes': total_classes,
                'official_percentage': round(official_percentage, 2),
            })

    # Calculate Overall data
    overall_attended = sum(item['attended_classes'] for item in subject_attendance_data)
    overall_absent = sum(item['absent_classes'] for item in subject_attendance_data)
    overall_on_duty = sum(item['on_duty_classes'] for item in subject_attendance_data)
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
    API-like view for the frontend to check for the latest unseen announcement.
    This version correctly targets users and excludes admins from pop-ups.
    """
    user = request.user
    # Admins or users without a profile won't get pop-up notifications
    if not hasattr(user, 'profile') or user.profile.role == 'admin':
        return JsonResponse({'found': False})

    # Base query for all announcements not yet seen by the user
    unseen_query = Announcement.objects.exclude(usernotificationstatus__user=user)

    # Build the filter based on the user's role and group
    target_filter = Q()  # Start with an empty Q object

    if user.profile.role == 'student' and user.profile.student_group:
        target_filter = Q(send_to_all_students=True) | Q(target_student_groups=user.profile.student_group)
    elif user.profile.role == 'faculty':
        target_filter = Q(send_to_all_faculty=True)

    # If the user is in a role that doesn't match, the filter remains empty,
    # and the query will correctly return no announcements.
    if not target_filter:
        return JsonResponse({'found': False})

    # Find the latest announcement that matches the criteria
    latest_announcement = unseen_query.filter(target_filter).distinct().order_by('-created_at').first()

    if latest_announcement:
        # Mark this announcement as seen for this user to prevent re-notification
        UserNotificationStatus.objects.get_or_create(user=user, announcement=latest_announcement)
        return JsonResponse({
            'found': True,
            'title': latest_announcement.title,
            'content': latest_announcement.content,
        })

    return JsonResponse({'found': False})


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
            (Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query) | Q(profile__student_id_number__icontains=query))
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
