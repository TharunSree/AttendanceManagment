from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages

from academics.models import Course, StudentGroup, Subject, Timetable, AttendanceRecord, DailySubstitution, \
    ClassCancellation, AttendanceSettings
from .decorators import nav_item
from .forms import AddTeacherForm, EditTeacherForm


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].widget.attrs.update({'class': 'form-control'})


def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, f"Welcome back, {username}!")
                return redirect('/')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('accounts:login')


def home(request):
    # This is a simple placeholder. You should have a proper home view.
    return render(request, 'index.html')


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
        form = AddTeacherForm(request.POST)
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
        form = EditTeacherForm(request.POST, instance=teacher_user.profile)
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

    # --- (The existing logic for fetching permissions remains the same) ---
    managed_models = [
        Course, Subject, StudentGroup, User,
        Timetable, AttendanceRecord, DailySubstitution, ClassCancellation,
        AttendanceSettings
    ]
    content_types = ContentType.objects.get_for_models(*managed_models).values()
    all_permissions = Permission.objects.filter(content_type__in=content_types)
    group_permissions = group.permissions.all()
    permissions_by_model = []
    for ct in content_types:
        model_perms = {
            'name': ct.model_class()._meta.verbose_name_plural.title(),
            'view': all_permissions.filter(content_type=ct, codename__startswith='view_').first(),
            'add': all_permissions.filter(content_type=ct, codename__startswith='add_').first(),
            'change': all_permissions.filter(content_type=ct, codename__startswith='change_').first(),
            'delete': all_permissions.filter(content_type=ct, codename__startswith='delete_').first(),
        }
        permissions_by_model.append(model_perms)

    if request.method == 'POST':
        # --- (The POST handling logic remains the same) ---
        selected_permission_ids = request.POST.getlist('permissions')
        selected_permissions = Permission.objects.filter(pk__in=selected_permission_ids)
        group.permissions.set(selected_permissions)
        messages.success(request, f"Permissions for group '{group.name}' updated successfully.")
        return redirect('accounts:group_permission_list')

    context = {
        'group': group,
        'permissions_by_model': permissions_by_model,
        'group_permissions': group_permissions,
        # --- FIX: Add the action lists to the context ---
        'actions': ["View", "Add", "Update", "Delete"],
        'action_codes': ["view", "add", "change", "delete"],
    }
    return render(request, 'accounts/group_permission_edit.html', context)
