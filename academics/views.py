# In academics/views.py
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

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
    students = student_group.students.all().order_by('first_name', 'last_name')
    attendance_settings = AttendanceSettings.load()
    required_percentage = attendance_settings.required_percentage

    # Get all timetable entries for the student's group
    total_classes_count = Timetable.objects.filter(student_group=student_group).count()

    students_with_attendance = []
    for student in students:
        # Get all present records for the student in this group's timetabled classes
        present_count = AttendanceRecord.objects.filter(
            student=student,
            timetable__student_group=student_group,
            status='Present'
        ).count()

        percentage = (present_count / total_classes_count * 100) if total_classes_count > 0 else 0

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
    student_group = student.student_groups.first()

    subject_attendance_data = []

    if student_group:
        # Get all subjects that are part of the student's course
        course_subjects = CourseSubject.objects.filter(course=student_group.course)

        for cs in course_subjects:
            # 1. Count total scheduled classes for THIS subject in the timetable for this class
            total_classes = Timetable.objects.filter(
                student_group=student_group,
                subject=cs
            ).count()

            # 2. Count 'Present' records for this student for this subject
            present_classes = AttendanceRecord.objects.filter(
                student=student,
                timetable__subject=cs,
                status='Present'
            ).count()

            # 3. Count 'Absent' records for this student for this subject
            absent_classes = AttendanceRecord.objects.filter(
                student=student,
                timetable__subject=cs,
                status='Absent'
            ).count()

            subject_attendance_data.append({
                'subject_pk': cs.subject.pk,
                'subject_name': cs.subject.name,
                'subject_code': cs.subject.code,
                'total_classes': total_classes,
                'present_classes': present_classes,
                'absent_classes': absent_classes,
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
            messages.success(request, f'Class "{student_group.name()}" has been updated.')
            return redirect('academics:admin_select_class')
    else:
        form = StudentGroupForm(instance=student_group)

    context = {
        'form': form,
        'form_title': f'Edit Class: {student_group.name()}'
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
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Course created successfully.')
            return redirect('academics:course_list')
    else:
        form = CourseForm()
    return render(request, 'academics/course_form.html', {'form': form, 'form_title': 'Create New Course'})

@login_required
@admin_required
def course_update_view(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Course updated successfully.')
            return redirect('academics:course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'academics/course_form.html', {'form': form, 'form_title': f'Edit Course: {course.name}'})


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
            # Create the User object. The signal will automatically create the profile.
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name']
            )

            # --- The Profile is now created automatically by the signal! ---
            # We just need to update the extra details from the form.
            user.profile.student_id_number = form.cleaned_data['student_id_number']
            user.profile.contact_number = form.cleaned_data['contact_number']
            user.profile.save()  # Save the updated profile details

            # Add the new student to the class
            student_group.students.add(user)

            messages.success(request, f"Student '{user.username}' created and added to the class successfully.")
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
    return render(request, 'academics/confirm_delete.html', {'item': student_group, 'type': 'Class'})


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


