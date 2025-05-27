from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login  # Renaming to avoid conflict
from django.contrib.auth.forms import AuthenticationForm  # Django's default login form
from django.contrib import messages



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