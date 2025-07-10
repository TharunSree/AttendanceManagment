import csv
import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from academics.email_utils import send_database_email
from academics.models import Course, StudentGroup, Subject, Timetable, AttendanceRecord, DailySubstitution, \
    ClassCancellation, AttendanceSettings, CourseSubject, Mark, Criterion, MarkingScheme, ExtraClass, ResultPublication, \
    LowAttendanceNotification
from .decorators import nav_item
from .forms import AddTeacherForm, EditTeacherForm, UserUpdateForm, ProfileUpdateForm, BulkImportForm, \
    CustomPasswordResetForm
from .models import Profile, Notification, UserActivityLog


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].widget.attrs.update({'class': 'form-control'})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:home')

    # Get the 'next' parameter from the GET request
    next_url = request.GET.get('next')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            if user is not None:
                auth_login(request, user)
                messages.info(request, f"Welcome back, {user.get_full_name() or user.username}.")

                # Get the 'next' parameter from the POST request (from the hidden input)
                next_url_post = request.POST.get('next')
                print(next_url_post)
                if next_url_post != 'None':
                    return redirect(next_url_post)
                return redirect('accounts:home')
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()

    # Pass the 'next' url to the template context
    return render(request, 'accounts/Login.html', {'form': form, 'next': next_url})


def logout_view(request):
    UserActivityLog.objects.create(
        user=request.user,
        username=request.user.username,
        action='logout',
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT')
    )
    auth_logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('accounts:login')


@login_required
@nav_item(title="Dashboard", icon="iconsminds-shop-4", url_name="accounts:home", order=0)
def home_view(request):
    """
    Redirects users to their appropriate dashboard after login.
    """
    if hasattr(request.user, 'profile'):
        if request.user.profile.role == 'admin':
            return redirect('accounts:admin_dashboard')
        elif request.user.profile.role == 'faculty':
            return redirect('accounts:faculty_dashboard')
        elif request.user.profile.role == 'student':
            return redirect('accounts:student_dashboard')

    # Fallback for superusers or users without a profile role
    return redirect('accounts:admin_dashboard')


@login_required
@permission_required('auth.view_user', raise_exception=True)
@nav_item(title="Manage Teachers", icon="simple-icon-people", url_name='accounts:teacher_list',
          permission='auth.view_user', group='admin_management', order=10)
def teacher_list_view(request):
    teachers = User.objects.filter(profile__role='faculty').prefetch_related('profile__field_of_expertise')
    return render(request, 'accounts/teacher_list.html', {'teachers': teachers})


@login_required
@permission_required('auth.add_user', raise_exception=True)
@transaction.atomic
def teacher_create_view(request):
    if request.method == 'POST':
        form = AddTeacherForm(request.POST, request.FILES)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                is_staff=True  # Teachers should be staff to access certain areas if needed later
            )
            user.profile.role = 'faculty'
            user.profile.contact_number = form.cleaned_data['contact_number']
            user.profile.save()
            user.profile.field_of_expertise.set(form.cleaned_data['field_of_expertise'])
            messages.success(request, 'Faculty member created successfully.')
            return redirect('accounts:teacher_list')
    else:
        form = AddTeacherForm()
    return render(request, 'accounts/teacher_form.html', {'form': form})


@login_required
@permission_required('auth.delete_user', raise_exception=True)
def teacher_delete_view(request, pk):
    teacher = get_object_or_404(User, pk=pk, profile__role='faculty')
    if request.method == 'POST':
        teacher.delete()
        messages.success(request, 'Faculty member has been deleted.')
        return redirect('accounts:teacher_list')
    return render(request, 'academics/confirm_delete.html', {'item': teacher, 'type': 'Faculty Member'})


@login_required
@permission_required('auth.change_user', raise_exception=True)
def teacher_update_view(request, pk):
    teacher_user = get_object_or_404(User, pk=pk, profile__role='faculty')
    if request.method == 'POST':
        form = EditTeacherForm(request.POST, request.FILES, instance=teacher_user.profile)
        if form.is_valid():
            form.save()
            teacher_user.first_name = form.cleaned_data['first_name']
            teacher_user.last_name = form.cleaned_data['last_name']
            teacher_user.email = form.cleaned_data['email']
            teacher_user.save()
            messages.success(request, f'Details for {teacher_user.get_full_name()} updated successfully.')
            return redirect('accounts:teacher_list')
    else:
        form = EditTeacherForm(instance=teacher_user.profile,
                               initial={
                                   'first_name': teacher_user.first_name,
                                   'last_name': teacher_user.last_name,
                                   'email': teacher_user.email
                               })
    context = {
        'form': form,
        'form_title': f'Edit Teacher: {teacher_user.get_full_name()}',
    }
    return render(request, 'accounts/teacher_form.html', context)


@login_required
@permission_required('auth.view_group', raise_exception=True)
@nav_item(title="Group Permissions", icon="iconsminds-administrator", url_name="accounts:group_permission_list",
          permission='auth.view_group', group='admin_management', order=5)
def group_permission_list_view(request):
    """
    Displays a list of all user groups.
    """
    groups = Group.objects.all().order_by('name')
    return render(request, 'accounts/group_permission_list.html', {'groups': groups})


@login_required
@permission_required('auth.change_group', raise_exception=True)
def group_permission_edit_view(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    # --- This list of models remains the same ---
    managed_models = [
        User, Course, Subject, StudentGroup, Timetable, AttendanceRecord,
        ClassCancellation, DailySubstitution, AttendanceSettings,
        Mark, Criterion, MarkingScheme, Profile, ExtraClass, Notification, ResultPublication,
        UserActivityLog, LowAttendanceNotification
    ]

    # Get all permissions related to our apps for a complete list
    content_types = ContentType.objects.get_for_models(*managed_models)
    all_app_permissions = Permission.objects.filter(content_type__in=content_types.values())

    # --- The logic to organize permissions is now improved ---
    permissions_by_model = []
    other_permissions = []

    # Keep track of standard permissions we have processed
    processed_perms = set()

    # Organize standard model permissions (add, change, delete, view)
    model_content_types = ContentType.objects.get_for_models(*managed_models)
    for ct in model_content_types.values():
        model_class = ct.model_class()
        if not model_class:
            continue

        model_name_lower = model_class._meta.model_name
        perms_for_model = all_app_permissions.filter(content_type=ct)

        model_perms_dict = {
            'name': model_class._meta.verbose_name_plural.title(),
            'view': perms_for_model.filter(codename=f'view_{model_name_lower}').first(),
            'add': perms_for_model.filter(codename=f'add_{model_name_lower}').first(),
            'change': perms_for_model.filter(codename=f'change_{model_name_lower}').first(),
            'delete': perms_for_model.filter(codename=f'delete_{model_name_lower}').first(),
        }
        permissions_by_model.append(model_perms_dict)

        # Add the processed permissions to our set
        for key, perm_object in model_perms_dict.items():
            if key != 'name' and perm_object:
                processed_perms.add(perm_object.pk)

    # Find all remaining permissions that are not standard add/change/view/delete
    other_permissions = all_app_permissions.exclude(id__in=processed_perms)

    # --- The POST logic remains the same ---
    if request.method == 'POST':
        selected_permission_ids = request.POST.getlist('permissions')
        selected_permissions = Permission.objects.filter(pk__in=selected_permission_ids)
        group.permissions.set(selected_permissions)
        messages.success(request, f"Permissions for group '{group.name}' updated successfully.")
        return redirect('accounts:group_permission_list')

    context = {
        'group': group,
        'permissions_by_model': sorted(permissions_by_model, key=lambda x: x['name']),
        'other_permissions': sorted(other_permissions, key=lambda x: x.name),
        'group_permissions': group.permissions.all(),
        'actions': ["View", "Add", "Update", "Delete"],
        'action_codes': ["view", "add", "change", "delete"],
    }
    return render(request, 'accounts/group_permission_edit.html', context)


@login_required
def admin_dashboard_view(request):
    today = timezone.now().date()

    # Top Row Stats
    total_students = Profile.objects.filter(role='student').count()
    total_faculty = Profile.objects.filter(role='faculty').count()
    total_courses = Course.objects.count()
    total_classes = StudentGroup.objects.count()

    # --- FIX: Provide the exact variables the script needs ---
    todays_records = AttendanceRecord.objects.filter(date=today)
    present_today = todays_records.filter(status='Present').count()
    on_duty_today = todays_records.filter(status='On Duty').count()

    # For the chart, consider all other statuses as 'absent'
    absent_today = todays_records.exclude(status__in=['Present', 'On Duty']).count()

    effective_total = present_today + absent_today  # Exclude On Duty from percentage
    attendance_today_percentage = (present_today / effective_total * 100) if effective_total > 0 else 0
    # --- END FIX ---

    recent_cancellations = ClassCancellation.objects.filter(date__lte=today).order_by('-date')[:5]
    recent_substitutions = DailySubstitution.objects.filter(date__lte=today).order_by('-date')[:5]

    context = {
        'total_students': total_students,
        'total_faculty': total_faculty,
        'total_courses': total_courses,
        'total_classes': total_classes,

        # Pass data with variable names expected by the script's "Overall Chart" call
        'overall_attended': present_today,
        'overall_absent': absent_today,
        'overall_on_duty': on_duty_today,
        'overall_official_percentage': attendance_today_percentage,

        'recent_cancellations': recent_cancellations,
        'recent_substitutions': recent_substitutions,
    }
    return render(request, 'accounts/admin_dashboard.html', context)


@login_required
def faculty_dashboard_view(request):
    today = timezone.now().date()
    current_day_str = today.strftime('%A')
    faculty_user = request.user

    # Today's Schedule (Regular + Substitutions)
    regular_classes = Timetable.objects.filter(faculty=faculty_user, day_of_week=current_day_str)
    substitution_classes = DailySubstitution.objects.filter(substituted_by=faculty_user, date=today)

    todays_schedule = list(regular_classes) + [sub.timetable for sub in substitution_classes]
    todays_schedule.sort(key=lambda x: x.time_slot.start_time)

    # Classes Today & Pending Attendance
    classes_today_count = len(todays_schedule)
    marked_timetable_ids = AttendanceRecord.objects.filter(
        marked_by=faculty_user, date=today
    ).values_list('timetable_id', flat=True).distinct()

    pending_attendance_count = 0
    for entry in todays_schedule:
        if entry.id not in marked_timetable_ids:
            pending_attendance_count += 1

    context = {
        'classes_today_count': classes_today_count,
        'pending_attendance_count': pending_attendance_count,
        'todays_schedule': todays_schedule,
        'marked_timetable_ids': marked_timetable_ids,
        # 'notifications': [] # Placeholder for future notifications feature
    }
    return render(request, 'accounts/faculty_dashboard.html', context)


@login_required
def student_dashboard_view(request):
    student_user = request.user
    today = timezone.now().date()
    current_day_str = today.strftime('%A')
    student_group = student_user.profile.student_group

    # --- IMPLEMENTATION: Calculate real attendance data ---
    subject_attendance_data = []
    settings = AttendanceSettings.load()

    if student_group and student_group.course:
        # Default to the latest semester for the dashboard view
        latest_semester_num = CourseSubject.objects.filter(
            course=student_group.course
        ).order_by('-semester').values_list('semester', flat=True).first()

        if latest_semester_num:
            subjects_for_semester = CourseSubject.objects.filter(
                course=student_group.course, semester=latest_semester_num
            )
            for course_subject in subjects_for_semester:
                total_classes = AttendanceRecord.objects.filter(
                    timetable__student_group=student_group,
                    timetable__subject=course_subject
                ).values('date', 'timetable_id').distinct().count()

                student_records = AttendanceRecord.objects.filter(
                    student=student_user,
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
                    'absent_classes': absent_count if absent_count > 0 else 0,
                    'on_duty_classes': on_duty_count,
                    'official_percentage': round(official_percentage, 2),
                })

    # Calculate Overall data
    overall_attended = sum(item['attended_classes'] for item in subject_attendance_data)
    overall_absent = sum(item['absent_classes'] for item in subject_attendance_data)
    overall_on_duty = sum(item['on_duty_classes'] for item in subject_attendance_data)
    overall_total = overall_attended + overall_absent + overall_on_duty
    overall_effective_total = overall_total - overall_on_duty
    overall_official_percentage = (
            overall_attended / overall_effective_total * 100) if overall_effective_total > 0 else 0

    subjects_below_threshold = [
        item for item in subject_attendance_data if item['official_percentage'] < settings.required_percentage
    ]

    # Today's Classes
    todays_classes = Timetable.objects.filter(
        student_group=student_group, day_of_week=current_day_str
    ).order_by('time_slot__start_time')
    # --- END IMPLEMENTATION ---

    context = {
        'overall_official_percentage': overall_official_percentage,
        'overall_attended': overall_attended,
        'overall_absent': overall_absent,
        'overall_on_duty': overall_on_duty,
        'subjects_below_threshold': subjects_below_threshold,
        'todays_classes': todays_classes,
        'subject_attendance_data_json': json.dumps(subject_attendance_data)
    }
    return render(request, 'accounts/student_dashboard.html', context)


@login_required
@permission_required('auth.change_user', raise_exception=True)
def admin_trigger_password_reset_view(request, user_id):
    """
    Allows an admin to manually trigger a password reset email for a user.
    """
    user = get_object_or_404(User, pk=user_id)

    # === THIS IS THE CORRECTED LINE ===
    # Use our custom form which knows how to send emails via the database settings
    form = CustomPasswordResetForm({'email': user.email})
    # ==================================

    if form.is_valid():
        opts = {
            'use_https': request.is_secure(),
            'request': request,
            'subject_template_name': 'registration/password_reset_subject.txt',
            'email_template_name': 'registration/password_reset_email.txt',
            'html_email_template_name': 'registration/password_reset_email.html',
        }

        # Now, when form.save() is called, it will correctly use the
        # send_mail method we defined in CustomPasswordResetForm.
        form.save(**opts)

        messages.success(request, f"A password reset email has been sent to {user.email}.")
    else:
        messages.error(request, "Could not trigger a password reset for this user.")

    return redirect(request.META.get('HTTP_REFERER', 'accounts:teacher_list'))


@login_required
def account_view(request):
    """
    Displays the user's own account information and allows them to update it.
    """
    user_form = UserUpdateForm(instance=request.user)
    profile_form = ProfileUpdateForm(instance=request.user.profile)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your account has been updated successfully.')
            return redirect('accounts:account_view')
        else:
            messages.error(request, 'Please correct the errors below.')

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'accounts/account_view.html', context)


@login_required
@permission_required('auth.add_user')
@nav_item(title="Bulk Import Users", icon="iconsminds-up", url_name="accounts:bulk_user_import",
          permission='auth.add_user', group='admin_management')
def bulk_user_import_view(request):
    if request.method == 'POST':
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['file']
            try:
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
            except Exception as e:
                messages.error(request, f"Error reading or decoding file: {e}")
                return redirect('accounts:bulk_user_import')

            success_count = 0
            error_list = []

            for row_num, row in enumerate(reader, 2):
                username = row.get('username')
                student_group_name = row.get('student_group_name')

                if not username or not student_group_name:
                    error_list.append(f"Row {row_num}: 'username' and 'student_group_name' are required.")
                    continue

                if User.objects.filter(username=username).exists():
                    error_list.append(f"Row {row_num}: User '{username}' already exists.")
                    continue

                try:
                    student_group = StudentGroup.objects.get(name=student_group_name)
                except StudentGroup.DoesNotExist:
                    error_list.append(f"Row {row_num}: Class '{student_group_name}' not found.")
                    continue

                try:
                    # Each user is created in their own transaction to isolate errors
                    with transaction.atomic():
                        user = User.objects.create_user(
                            username=username,
                            password=row.get('password'),
                            first_name=row.get('first_name'),
                            last_name=row.get('last_name'),
                            email=row.get('email')
                        )

                        profile = user.profile
                        profile.role = 'student'
                        profile.student_id_number = row.get('student_id_number')
                        profile.contact_number = row.get('contact_number')
                        profile.student_group = student_group
                        profile.address = row.get('address')
                        profile.father_name = row.get('father_name')
                        profile.father_phone = row.get('father_phone')
                        profile.mother_name = row.get('mother_name')
                        profile.mother_phone = row.get('mother_phone')
                        profile.gender = row.get('gender')
                        profile.parent_email = row.get('parent_email')

                        # --- Robust Date of Birth Handling ---
                        dob_str = row.get('date_of_birth')
                        if dob_str:
                            try:
                                # First, try the standard YYYY-MM-DD format
                                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    # If that fails, try the dd-mm-yyyy format from Excel
                                    dob = datetime.strptime(dob_str, '%d-%m-%Y').date()
                                except ValueError:
                                    raise Exception("Invalid 'date_of_birth' format. Please use YYYY-MM-DD.")
                            profile.date_of_birth = dob

                        profile.save()

                    # --- Send Welcome Email (outside the transaction) ---
                    if user.email:
                        login_url = request.build_absolute_uri(reverse('accounts:login'))
                        email_context = {
                            'user': user,
                            'username': username,
                            'password': row.get('password'),
                            'login_url': login_url
                        }
                        html_content = render_to_string('emails/new_user_welcome.html', email_context)
                        plain_text_content = f"Welcome! Your username is {username} and your password is {row.get('password')}. Please log in and change it."

                        send_database_email(
                            subject="Your New Account Details",
                            body=plain_text_content,
                            recipient_list=[user.email],
                            html_message=html_content
                        )

                    success_count += 1

                except Exception as e:
                    error_list.append(f"Row {row_num}: Failed to import user {username}. Error: {e}")

            if success_count > 0:
                messages.success(request, f"Successfully imported and notified {success_count} students.")
            if error_list:
                messages.warning(request, f"Import finished with {len(error_list)} errors.")

            return render(request, 'accounts/bulk_user_import.html', {'form': BulkImportForm(), 'errors': error_list})
    else:
        form = BulkImportForm()

    return render(request, 'accounts/bulk_user_import.html', {'form': form})


@login_required
@permission_required('auth.add_user')
def download_csv_template_view(request):
    """
    Generates and serves a blank CSV template with the corrected header order.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'

    writer = csv.writer(response)

    # === THIS IS THE UPDATED HEADER ROW ===
    writer.writerow([
        'username', 'password', 'first_name', 'last_name', 'date_of_birth', 'gender', 'email',
        'student_id_number', 'contact_number', 'student_group_name',
        'address', 'father_name', 'father_phone', 'mother_name', 'mother_phone', 'parent_email'
    ])
    # ======================================

    return response


@login_required
def mark_notifications_as_read_view(request):
    if request.method == 'POST':
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
