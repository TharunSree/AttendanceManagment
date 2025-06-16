from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login  # Renaming to avoid conflict
from django.contrib.auth.forms import AuthenticationForm  # Django's default login form
from django.contrib import messages

from accounts.decorators import admin_required
from accounts.forms import AddTeacherForm


# This is your custom form that you use in the view.
# It inherits from Django's AuthenticationForm and customizes widget attributes.
class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].widget.attrs.update({'class': 'form-control'})


def login_view(request):
    if request.method == 'POST':
        # Use your CustomAuthenticationForm when handling a POST request
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)  # Logs the user in
                messages.success(request, f"Welcome back, {username}!")
                # FUTURE: Implement role-based redirection here
                # profile = user.profile
                # if profile.role == 'admin':
                #     return redirect('admin_dashboard_url_name')
                # elif profile.role == 'faculty':
                #     return redirect('faculty_dashboard_url_name')
                # else:
                #     return redirect('student_dashboard_url_name')
                return redirect('/')  # Currently redirects to homepage
            else:
                messages.error(request, "Invalid username or password.")
        else:
            # Form is not valid (e.g., fields missing)
            messages.error(request, "Invalid username or password.")  # Or more specific errors from form.errors
    else:
        # For a GET request (when the user first visits the login page),
        # create an instance of your CustomAuthenticationForm
        form = CustomAuthenticationForm()

    # Render the login template, passing the form instance to it.
    # The template path 'accounts/Login.html' matches the location of your Dore-styled login page.
    return render(request, 'accounts/login.html', {'form': form})


# We will also need a logout view
from django.contrib.auth import logout as auth_logout


def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login')  # Redirects to the login page, 'login' is the name of your login URL

def home(request):
    return HttpResponse("Hello, world!")

@login_required
@admin_required
def teacher_list_view(request):
    # Get all users who have a profile with the role 'faculty'
    teachers = User.objects.filter(profile__role='faculty')
    return render(request, 'accounts/teacher_list.html', {'teachers': teachers})


@login_required
@admin_required
@transaction.atomic
def teacher_create_view(request):
    if request.method == 'POST':
        form = AddTeacherForm(request.POST)
        if form.is_valid():
            # The User is created first.
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name']
            )
            # The signal automatically creates a Profile. Now we update it.
            user.profile.role = 'faculty'  # Set the role to faculty
            user.profile.contact_number = form.cleaned_data['contact_number']
            user.profile.save()

            messages.success(request, 'Faculty member created successfully.')
            return redirect('teacher_list')
    else:
        form = AddTeacherForm()

    return render(request, 'accounts/teacher_form.html', {'form': form})


@login_required
@admin_required
def teacher_delete_view(request, pk):
    teacher = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        # The user's profile will be deleted automatically because of the CASCADE setting
        teacher.delete()
        messages.success(request, 'Faculty member has been deleted.')
        return redirect('accounts:teacher_list')

    # We can reuse the generic confirm delete template
    return render(request, 'academics/confirm_delete.html', {'item': teacher, 'type': 'Faculty Member'})