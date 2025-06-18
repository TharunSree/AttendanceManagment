# In academics/views.py
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.forms import inlineformset_factory
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms

from academics.forms import EditStudentForm
from accounts.models import Profile
from .forms import StudentGroupForm, CourseForm, AddStudentForm, SubjectForm
from .models import StudentGroup, AttendanceSettings, Course, Subject, \
    Timetable, AttendanceRecord, CourseSubject
from accounts.decorators import admin_required
import json


# ... other views ...

@login_required
@admin_required
def admin_student_list_view(request, group_id):
    student_group = get_object_or_404(StudentGroup, pk=group_id)
    students = User.objects.filter(profile__student_group=student_group).order_by('first_name', 'last_name')
    attendance_settings = AttendanceSettings.load()
    required_percentage = attendance_settings.required_percentage

    students_with_attendance = []
    for student in students:
        total_classes_taken = AttendanceRecord.objects.filter(
            student=student,
            timetable__student_group=student_group
        ).count()
        # Get all present records for the student in this group's timetabled classes
        present_count = AttendanceRecord.objects.filter(
            student=student,
            timetable__student_group=student_group,
            status='Present'
        ).count()

        percentage = (present_count / total_classes_taken * 100) if total_classes_taken > 0 else 0

        students_with_attendance.append({
            'student': student,
            'attendance_percentage': percentage,
        })

    show_low_attendance_only = request.GET.get('low_attendance_filter') == 'on'
    if show_low_attendance_only:
        students_with_attendance = [
            s_data for s_data in students_with_attendance
            if s_data['attendance_percentage'] < required_percentage
        ]

    context = {
        'student_group': student_group,
        'students_with_attendance': students_with_attendance,
        'required_percentage': required_percentage,
        'show_low_attendance_only': show_low_attendance_only,
        'total_students': len(students),
    }
    return render(request, 'academics/admin_student_list.html', context)


@login_required
@admin_required
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
@admin_required
def admin_student_attendance_detail_view(request, student_id):
    student = get_object_or_404(User, pk=student_id)
    student_group = None
    if hasattr(student, 'profile') and student.profile.student_group:
        student_group = student.profile.student_group

    subject_attendance_data = []

    if student_group and student_group.course:
        # Get all CourseSubject instances for the student's course
        all_course_subjects = CourseSubject.objects.filter(course=student_group.course)

        # Check which subjects have timetable entries
        timetable_coursesubject_ids = set(
            Timetable.objects.filter(student_group=student_group)
            .values_list('subject_id', flat=True)
        )

        for course_subject_instance in all_course_subjects:
            # Check if this subject has timetable entries
            if course_subject_instance.id in timetable_coursesubject_ids:
                # Calculate attendance as before
                total_classes = AttendanceRecord.objects.filter(
                    timetable__student_group=student_group,
                    timetable__subject=course_subject_instance
                ).values('date').distinct().count()

                attended_classes = AttendanceRecord.objects.filter(
                    student=student,
                    timetable__student_group=student_group,
                    timetable__subject=course_subject_instance,
                    status='Present'
                ).count()
            else:
                # No timetable entries yet - show as 0/0
                total_classes = 0
                attended_classes = 0

            subject_attendance_data.append({
                'subject_pk': course_subject_instance.subject.pk,
                'subject_name': course_subject_instance.subject.name,
                'subject_code': course_subject_instance.subject.code,
                'total_classes': total_classes,
                'attended_classes': attended_classes,
                'has_timetable': course_subject_instance.id in timetable_coursesubject_ids,
            })

    context = {
        'student': student,
        'student_group': student_group,
        'subject_attendance_data': subject_attendance_data,
        'subject_attendance_data_json': json.dumps(subject_attendance_data),
    }
    return render(request, 'academics/admin_student_attendance_detail.html', context)

@login_required
@admin_required
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
@admin_required
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
@admin_required
def course_list_view(request):
    courses = Course.objects.all()
    return render(request, 'academics/course_list.html', {'courses': courses})


@login_required
@admin_required
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
@admin_required
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
@admin_required
def course_delete_view(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Course deleted successfully.')
        return redirect('academics:course_list')
    return render(request, 'academics/course_confirm_delete.html', {'course': course})


@login_required
@admin_required
def student_group_delete_view(request, pk):
    student_group = get_object_or_404(StudentGroup, pk=pk)
    if request.method == 'POST':
        student_group.delete()
        messages.success(request, 'Class deleted successfully.')
        return redirect('academics:admin_select_class')
    return render(request, 'academics/student_group_confirm_delete.html', {'student_group': student_group})


@login_required
@admin_required
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
@admin_required
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
@admin_required
def student_group_delete_view(request, pk):
    student_group = get_object_or_404(StudentGroup, pk=pk)
    if request.method == 'POST':
        student_group.delete()
        messages.success(request, f'Class "{student_group.name}" has been deleted.')
        return redirect('academics:admin_select_class')
    return render(request, 'academics/student_group_confirm_delete.html', {'student_group': student_group})


@login_required
@admin_required
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
@admin_required
def subject_list_view(request):
    subjects = Subject.objects.all().order_by('name')
    return render(request, 'academics/subject_list.html', {'subjects': subjects})


@login_required
@admin_required
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
@admin_required
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
@admin_required
def subject_delete_view(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted successfully.')
        return redirect('academics:subject_list')
    return render(request, 'academics/confirm_delete.html', {'item': subject, 'type': 'Subject'})


@login_required
@admin_required
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