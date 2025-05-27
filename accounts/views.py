from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login # Renaming to avoid conflict
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages


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
                # Redirect to a success page.
                # For now, let's redirect to a hypothetical 'dashboard'
                # We'll create this URL/view later.
                messages.success(request, f"Welcome back, {username}!")
                # You might want to redirect based on role here in the future
                # For example:
                # profile = user.profile
                # if profile.role == 'admin':
                #     return redirect('admin_dashboard')
                # elif profile.role == 'faculty':
                #     return redirect('faculty_dashboard')
                # else:
                #     return redirect('student_dashboard')
                return redirect('/') # For now, redirect to homepage
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()
    # In AttendanceManagment/accounts/views.py, inside login_view function
    return render(request, 'accounts/Login.html', {'form': form})

# We will also need a logout view
from django.contrib.auth import logout as auth_logout



def logout_view(request):
    auth_logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect('login') # Or wherever you want to redirect after logout


def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # This saves the new User object
            # Optionally, log the user in directly after registration
            auth_login(request, user)
            messages.success(request, "Registration successful! You are now logged in.")
            # Redirect to a success page, e.g., homepage or a dashboard
            # For now, let's redirect to the homepage '/'
            return redirect('/')
        else:
            # Form is invalid, re-render the page with error messages
            for field in form:
                for error in field.errors:
                    messages.error(request, f"{field.label}: {error}")
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = UserCreationForm()
    return render(request, 'accounts/Register.html', {'form': form})


# views.py
from django.http import HttpResponse

def home(request):
    return HttpResponse("Hello, world!")
