from django import forms
from django.contrib.auth.models import User

from accounts.models import Profile
from .models import Course, StudentGroup, Subject, AttendanceRecord, CourseSubject, AttendanceSettings, TimeSlot, \
    Timetable

from django import forms
from django.contrib.auth.models import User

# --- NEW: Custom form field to display user's full name ---
class UserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name()

class StudentGroupForm(forms.ModelForm):
    class Meta:
        model = StudentGroup
        fields = ['name', 'course', 'start_year', 'passout_year']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., BCA Section A'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'start_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024'}),
            'passout_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2028'}),
        }


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'course_type', 'duration_years', 'required_hours_per_semester', 'description']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'course_type': forms.Select(attrs={'class': 'form-control'}),
            'duration_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'required_hours_per_semester': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class AddStudentForm(forms.Form):
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)

    student_id_number = forms.CharField(max_length=20, required=True,
                                        widget=forms.TextInput(attrs={'class': 'form-control'}))
    contact_number = forms.CharField(max_length=15, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))

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
        fields = ['name', 'code', 'subject_type', 'description', 'required_hours']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'subject_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'required_hours': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# In academics/forms.py
class MarkAttendanceForm(forms.Form):
    # --- THIS IS THE FIX ---
    # We use the choices directly from the model without adding a blank option
    status = forms.ChoiceField(
        choices=AttendanceRecord.STATUS_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'custom-control-input'}),
        required=True
    )
    student_id = forms.IntegerField(widget=forms.HiddenInput())


class EditStudentForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Profile
        fields = ['student_id_number', 'contact_number']
        widgets = {
            'student_id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['start_time', 'end_time', 'label','is_schedulable']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "e.g., LUNCH"}),
            'is_schedulable': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
        }


class AttendanceSettingsForm(forms.ModelForm):
    class Meta:
        model = AttendanceSettings
        fields = ['required_percentage', 'mark_deadline_days', 'edit_deadline_days']
        widgets = {
            'required_percentage': forms.NumberInput(attrs={'class': 'form-control'}),
            'mark_deadline_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'edit_deadline_days': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# In academics/forms.py

class TimetableEntryForm(forms.ModelForm):
    # Use the custom field to show full names and filter by Group membership
    faculty = UserChoiceField(
        queryset=User.objects.filter(groups__name='Faculty').order_by('first_name'),
        widget=forms.Select(attrs={'class': 'form-control select2-single'}),
        label="Faculty"
    )

    class Meta:
        model = Timetable
        fields = ['subject', 'faculty']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-control select2-single'}),
        }

    def __init__(self, *args, **kwargs):
        student_group = kwargs.pop('student_group', None)
        super().__init__(*args, **kwargs)

        if student_group:
            # This logic correctly filters subjects to the latest semester
            latest_semester_instance = CourseSubject.objects.filter(
                course=student_group.course
            ).order_by('-semester').first()

            queryset = CourseSubject.objects.none()
            if latest_semester_instance:
                queryset = CourseSubject.objects.filter(
                    course=student_group.course,
                    semester=latest_semester_instance.semester
                ).select_related('subject').order_by('subject__name')

            self.fields['subject'].queryset = queryset

class SubstitutionForm(forms.Form):
    # This field will be a dropdown of all users who are faculty members.
    substitute_faculty = UserChoiceField(
        queryset=User.objects.filter(profile__role='faculty'),
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
        label=""
    )
