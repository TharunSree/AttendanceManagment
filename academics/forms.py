from django import forms
from django.contrib.auth.models import User

from accounts.models import Profile
from .models import Course, StudentGroup, Subject, AttendanceRecord


class StudentGroupForm(forms.ModelForm):
    class Meta:
        model = StudentGroup
        # Add 'name' and remove 'students'
        fields = ['name', 'course', 'start_year', 'passout_year']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., BCA Section A'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'start_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024'}),
            'passout_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2028'}),
        }


class CourseForm(forms.ModelForm):
    # This allows for a multi-select box for subjects
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.SelectMultiple(
            attrs={'class': 'form-control select2-multiple', 'data-placeholder': 'Select Subjects...'}),
        required=False
    )

    class Meta:
        model = Course
        fields = ['name', 'course_type', 'duration_years', 'required_hours_per_semester', 'description', 'subjects']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'course_type': forms.Select(attrs={'class': 'form-control'}),
            'duration_years': forms.TextInput(attrs={'class': 'form-control'}),
            'required_hours_per_semester': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# --- ADD THIS NEW FORM FOR CREATING STUDENTS ---
class AddStudentForm(forms.Form):
    # Fields for the User model
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)

    # Fields for the Profile model
    student_id_number = forms.CharField(max_length=20, required=True,
                                        widget=forms.TextInput(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=15, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))

    # Add a clean method to check for existing username or email to give better errors
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email address already exists.")
        return email

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }

class MarkAttendanceForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput())
    # This line needs AttendanceRecord to be imported to work
    status = forms.ChoiceField(
        choices=AttendanceRecord.STATUS_CHOICES,
        widget=forms.RadioSelect,
        required=True
    )


