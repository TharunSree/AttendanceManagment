from django import forms
from django.contrib.auth.models import User, Group
import datetime

from django.forms import inlineformset_factory

from accounts.models import Profile
from .models import Course, StudentGroup, Subject, AttendanceRecord, CourseSubject, AttendanceSettings, TimeSlot, \
    Timetable, Announcement, MarkingScheme, Criterion, ExtraClass

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
        fields = ['name', 'course_type', 'duration_years', 'required_hours_per_semester', 'description',
                  'marking_scheme']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'course_type': forms.Select(attrs={'class': 'form-control'}),
            'duration_years': forms.NumberInput(attrs={'class': 'form-control'}),
            'required_hours_per_semester': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'marking_scheme': forms.Select(attrs={'class': 'form-control'}),
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

    # --- NEW FIELDS TO ADD ---
    photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control-file'}))
    father_name = forms.CharField(max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    father_phone = forms.CharField(max_length=15, required=False,
                                   widget=forms.TextInput(attrs={'class': 'form-control'}))
    mother_name = forms.CharField(max_length=100, required=False,
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    mother_phone = forms.CharField(max_length=15, required=False,
                                   widget=forms.TextInput(attrs={'class': 'form-control'}))
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))

    # -------------------------

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
    is_late = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    student_id = forms.IntegerField(widget=forms.HiddenInput())


class EditStudentForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Profile
        # --- UPDATED FIELDS LIST ---
        fields = ['photo', 'student_id_number', 'contact_number', 'father_name', 'father_phone', 'mother_name',
                  'mother_phone', 'address']
        # ---------------------------
        widgets = {
            'student_id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control-file'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mother_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['start_time', 'end_time', 'label', 'is_schedulable']
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


class AttendanceReportForm(forms.Form):
    student_group = forms.ModelChoiceField(
        queryset=StudentGroup.objects.all(),
        empty_label="--- Select Class ---",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        empty_label="--- Select Subject ---",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    month = forms.ChoiceField(
        choices=[(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    year = forms.ChoiceField(
        choices=[(i, i) for i in range(datetime.date.today().year, 2020, -1)],
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class AnnouncementForm(forms.ModelForm):
    target_student_groups = forms.ModelMultipleChoiceField(
        queryset=StudentGroup.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Target Specific Classes"
    )

    class Meta:
        model = Announcement
        fields = ['title', 'content', 'target_student_groups', 'send_to_all_students', 'send_to_all_faculty']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'send_to_all_students': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'send_to_all_faculty': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
        }


class MarkingSchemeForm(forms.ModelForm):
    class Meta:
        model = MarkingScheme
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CriterionForm(forms.ModelForm):
    class Meta:
        model = Criterion
        fields = ['name', 'max_marks']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Internal Exam'}),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 50'}),
        }


# This creates a formset to manage multiple Criterion objects on the same page as the MarkingScheme
CriterionFormSet = inlineformset_factory(
    MarkingScheme,
    Criterion,
    form=CriterionForm,
    extra=1,  # Start with one extra form for a new criterion
    can_delete=True,
    can_delete_extra=True
)


class MarkSelectForm(forms.Form):
    student_group = forms.ModelChoiceField(
        queryset=StudentGroup.objects.none(),
        label="Class",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    course_subject = forms.ModelChoiceField(
        queryset=CourseSubject.objects.none(),
        label="Subject",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        # Pop the custom querysets from the kwargs before calling super()
        groups_queryset = kwargs.pop('groups_queryset', None)
        subjects_queryset = kwargs.pop('subjects_queryset', None)
        super(MarkSelectForm, self).__init__(*args, **kwargs)

        # Now, assign the querysets to the fields
        if groups_queryset is not None:
            self.fields['student_group'].queryset = groups_queryset
        if subjects_queryset is not None:
            self.fields['course_subject'].queryset = subjects_queryset


class BulkMarksImportForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'class': 'custom-file-input'}))


class MarksReportForm(forms.Form):
    student_group = forms.ModelChoiceField(
        queryset=StudentGroup.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    semester = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


# In academics/forms.py

class ExtraClassForm(forms.ModelForm):
    # ... (Meta class is unchanged) ...
    class Meta:
        model = ExtraClass
        fields = ['teacher', 'class_group', 'subject', 'date', 'time_slot']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'class_group': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time_slot': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        is_faculty = self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'faculty'

        self.fields['subject'].queryset = CourseSubject.objects.none()
        self.fields['time_slot'].queryset = TimeSlot.objects.filter(is_schedulable=True)

        teacher_to_filter = None

        if is_faculty:
            self.fields['teacher'].widget = forms.HiddenInput()
            self.initial['teacher'] = self.user.pk
            self.fields['teacher'].queryset = User.objects.filter(pk=self.user.pk)
            teacher_to_filter = self.user
        else:  # Admin logic
            self.fields['teacher'].queryset = User.objects.filter(profile__role='faculty').order_by('first_name')

            # --- FIX: Correctly determine the teacher to filter by ---
            # Priority: 1. POST data -> 2. GET filter data -> 3. Saved instance data
            teacher_id = None
            if self.is_bound and 'teacher' in self.data:
                teacher_id = self.data.get('teacher')
            elif 'teacher' in self.initial:
                teacher_id = self.initial.get('teacher')
            elif self.instance and self.instance.pk:
                teacher_id = self.instance.teacher_id

            if teacher_id:
                try:
                    teacher_to_filter = User.objects.get(pk=int(teacher_id))
                except (ValueError, TypeError, User.DoesNotExist):
                    pass  # teacher_to_filter will remain None, resulting in an empty subject list
            # --- END FIX ---

        # Now, populate the subjects dropdown if we have a teacher
        if teacher_to_filter:
            self.fields['subject'].queryset = CourseSubject.objects.filter(
                timetable_entries__faculty=teacher_to_filter
            ).select_related('subject', 'course').distinct().order_by('subject__name')

    # ... (The clean method is unchanged and correct) ...
    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get('teacher')
        subject = cleaned_data.get('subject')
        class_group = cleaned_data.get('class_group')
        date = cleaned_data.get('date')
        time_slot = cleaned_data.get('time_slot')

        if not all([teacher, subject, class_group, date, time_slot]):
            return cleaned_data

        day_of_week = date.strftime('%A')

        # Check for conflict with the regular timetable
        if Timetable.objects.filter(faculty=teacher, day_of_week=day_of_week, time_slot=time_slot).exists():
            self.add_error('time_slot', f"{teacher.get_full_name()} already has a scheduled class at this time.")

        if Timetable.objects.filter(student_group=class_group, day_of_week=day_of_week, time_slot=time_slot).exists():
            self.add_error('time_slot', f"{class_group.name} already has a scheduled class at this time.")

        # Build a base queryset for checking conflicts with other Extra Classes
        extra_class_conflicts = ExtraClass.objects.filter(date=date, time_slot=time_slot)

        # If we are editing an existing instance, we must exclude it from the conflict check
        if self.instance and self.instance.pk:
            extra_class_conflicts = extra_class_conflicts.exclude(pk=self.instance.pk)

        # Now, check for conflicts using the prepared queryset
        if extra_class_conflicts.filter(teacher=teacher).exists():
            self.add_error('time_slot', f"{teacher.get_full_name()} already has another extra class at this time.")
        if extra_class_conflicts.filter(class_group=class_group).exists():
            self.add_error('time_slot', f"{class_group.name} already has another extra class at this time.")

        # The existing validation for subject assignment is still relevant and correct
        if not CourseSubject.objects.filter(course=class_group.course, pk=subject.pk).exists():
            self.add_error('subject',
                           f"The subject '{subject.subject.name}' is not part of the '{class_group.course.name}' course.")

        return cleaned_data