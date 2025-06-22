# In academics/views.py
import json
from datetime import datetime
from itertools import chain

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import transaction
from django.forms import inlineformset_factory, formset_factory
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django import forms
from django.urls import reverse
from django.utils import timezone

from academics.forms import EditStudentForm, AttendanceSettingsForm, TimeSlotForm, MarkAttendanceForm, \
    TimetableEntryForm, SubstitutionForm
from accounts.models import Profile
from .forms import StudentGroupForm, CourseForm, AddStudentForm, SubjectForm
from .models import StudentGroup, AttendanceSettings, Course, Subject, \
    Timetable, AttendanceRecord, CourseSubject, TimeSlot, ClassCancellation, DailySubstitution
from accounts.decorators import nav_item


# ... other views ...

@login_required
@permission_required('academics.view_attendance_settings', raise_exception=True)
@nav_item(title="Attendance Settings", icon="iconsminds-gears", url_name="academics:admin_settings", permission='academics.view_attendance_settings',group='application_settings', order=1)
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
    students = User.objects.filter(profile__student_group=student_group).order_by('first_name', 'last_name')
    attendance_settings = AttendanceSettings.load()
    required_percentage = attendance_settings.required_percentage

    latest_semester_instance = CourseSubject.objects.filter(course=student_group.course).order_by('-semester').first()
    latest_semester_num = latest_semester_instance.semester if latest_semester_instance else None

    latest_semester_subjects_ids = []
    if latest_semester_num:
        latest_semester_subjects_ids = CourseSubject.objects.filter(
            course=student_group.course,
            semester=latest_semester_num
        ).values_list('id', flat=True)

    # --- NEW: Get total classes held for the entire group in the semester ---
    total_classes_held = AttendanceRecord.objects.filter(
        timetable__student_group=student_group,
        timetable__subject_id__in=latest_semester_subjects_ids
    ).values('timetable', 'date').distinct().count()
    # --- END NEW ---

    students_with_attendance = []
    for student in students:
        student_records = AttendanceRecord.objects.filter(
            student=student,
            timetable__student_group=student_group,
            timetable__subject_id__in=latest_semester_subjects_ids
        )

        present_count = student_records.filter(status='Present').count()
        on_duty_count = student_records.filter(status='On Duty').count()

        effective_total_classes = total_classes_held - on_duty_count
        percentage = (present_count / effective_total_classes * 100) if effective_total_classes > 0 else 0

        students_with_attendance.append({
            'student': student,
            'attendance_percentage': percentage,
        })

    # ... (rest of the view is the same)
    context = {
        'student_group': student_group,
        'students_with_attendance': students_with_attendance,
        'required_percentage': required_percentage,
        'show_low_attendance_only': request.GET.get('low_attendance_filter') == 'on',
        'total_students': len(students),
        'latest_semester_num': latest_semester_num,
    }
    return render(request, 'academics/admin_student_list.html', context)


@login_required
@permission_required('academics.view_studentgroup', raise_exception=True)
@nav_item(title="Manage Classes", icon="iconsminds-network", url_name="academics:admin_select_class", permission='academics.view_studentgroup', group='admin_management', order=30)
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
@nav_item(title="Manage Courses", icon="iconsminds-books", url_name='academics:course_list', permission='academics.view_course', group='admin_management', order=10)
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
@nav_item(title="Manage Subjects", icon="iconsminds-book", url_name='academics:subject_list', permission='academics.view_subject', group='admin_management', order=20)
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
def mark_attendance_view(request, timetable_id):
    timetable_entry = get_object_or_404(Timetable, pk=timetable_id)
    students = User.objects.filter(profile__student_group=timetable_entry.student_group).order_by('first_name')

    MarkAttendanceFormSet = formset_factory(MarkAttendanceForm, extra=0)
    current_date = timezone.now().date()

    # Prevent marking attendance for a cancelled class
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

                    AttendanceRecord.objects.update_or_create(
                        student=student,
                        timetable=timetable_entry,
                        date=current_date,
                        defaults={'status': status, 'marked_by': request.user}
                    )
            messages.success(request, "Attendance has been marked successfully.")
            return redirect('academics:faculty_schedule')
    else:
        # --- THIS IS THE FIX ---
        initial_data = []
        # Get all existing records for this session in a single, efficient query
        existing_records = AttendanceRecord.objects.filter(
            timetable=timetable_entry,
            date=current_date
        )
        # Create a dictionary mapping student_id to their saved status for quick lookup
        status_map = {record.student_id: record.status for record in existing_records}

        for student in students:
            # For each student, check if a status was already saved
            saved_status = status_map.get(student.id)
            initial_data.append({
                'student_id': student.id,
                # Use the saved status, or default to 'Present' if none exists
                'status': saved_status if saved_status else 'Present'
            })

        formset = MarkAttendanceFormSet(initial=initial_data)
        # --- END FIX ---

    student_forms = zip(students, formset)
    context = {
        'timetable_entry': timetable_entry,
        'formset': formset,
        'student_forms': student_forms
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

            # --- FIX: Added substitution info to the context for the template ---
            daily_log.append({
                'timetable': entry,
                'status': 'Conducted',
                'present_count': present_count,
                'total_students': total_students,
                'date': date,
                'substituted_by': sub_map.get(entry.id)  # Will be None if no sub exists
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
          group='admin_management', order=50)
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