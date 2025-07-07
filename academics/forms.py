import datetime

from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from accounts.models import Profile
from .models import Course, StudentGroup, Subject, AttendanceRecord, CourseSubject, AttendanceSettings, TimeSlot, \
    Timetable, Announcement, MarkingScheme, Criterion, ExtraClass, AcademicSession


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

    def clean(self):
        cleaned_data = super().clean()
        start_year = cleaned_data.get("start_year")
        passout_year = cleaned_data.get("passout_year")

        if start_year and passout_year:
            if start_year >= passout_year:
                raise forms.ValidationError(
                    "The passout year must be after the start year."
                )
        return cleaned_data


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
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}), )
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
    parent_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional parent email'})
    )

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
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}), )
    parent_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional parent email'})
    )

    class Meta:
        model = Profile
        # --- UPDATED FIELDS LIST ---
        fields = ['photo', 'student_id_number', 'contact_number', 'father_name', 'father_phone', 'mother_name',
                  'mother_phone', 'address', 'gender', 'date_of_birth', 'first_name', 'last_name', 'email',
                  'parent_email']
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
        fields = ['required_percentage', 'mark_deadline_days', 'edit_deadline_days', 'passing_percentage',
                  'cancellation_threshold_hours',
                  'number_of_backups_to_retain',
                  'session_timeout_seconds',
                  'notification_recipient_email',
                  ]
        widgets = {
            'required_percentage': forms.NumberInput(attrs={'class': 'form-control'}),
            'mark_deadline_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'edit_deadline_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'passing_percentage': forms.NumberInput(attrs={'class': 'form-control'}),
            'cancellation_threshold_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'number_of_backups_to_retain': forms.NumberInput(attrs={'class': 'form-control'}),
            'session_timeout_seconds': forms.NumberInput(attrs={'class': 'form-control'}),
            'notification_recipient_email': forms.EmailInput(
                attrs={'class': 'form-control', 'placeholder': 'e.g., admin@example.com'}),
        }


# In academics/forms.py

class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['subject', 'faculty']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'faculty': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Extract the student_group from kwargs if provided
        self.student_group = kwargs.pop('student_group', None)
        super().__init__(*args, **kwargs)

        if self.student_group:
            # Filter subjects to only those in the student group's course
            latest_semester = CourseSubject.objects.filter(
                course=self.student_group.course
            ).order_by('-semester').values_list('semester', flat=True).first()

            if latest_semester:
                self.fields['subject'].queryset = CourseSubject.objects.filter(
                    course=self.student_group.course,
                    semester=latest_semester
                )
            else:
                self.fields['subject'].queryset = CourseSubject.objects.none()

        # Initially set faculty to all faculty members
        self.fields['faculty'].queryset = User.objects.filter(
            profile__role='faculty'
        ).order_by('first_name')

        # If a subject is already selected (during edit), filter faculty accordingly
        if self.instance and self.instance.pk and self.instance.subject:
            self.fields['faculty'].queryset = self._get_faculty_for_subject(self.instance.subject)

    def _get_faculty_for_subject(self, subject):
        """Helper method to get faculty for a specific subject"""
        try:
            # Get faculty with matching specialization
            specialized_faculty = User.objects.filter(
                profile__role='faculty',
                profile__field_of_expertise=subject.subject
            ).order_by('first_name')

            # If no specialized faculty, return all faculty
            if specialized_faculty.exists():
                return specialized_faculty
            else:
                return User.objects.filter(
                    profile__role='faculty'
                ).order_by('first_name')
        except Exception:
            # Fallback to all faculty if there's any error
            return User.objects.filter(
                profile__role='faculty'
            ).order_by('first_name')

    # In your TimetableForm class (if you need custom validation)
    def clean(self):
        cleaned_data = super().clean()
        day_of_week = cleaned_data.get('day_of_week')
        time_slot = cleaned_data.get('time_slot')
        faculty = cleaned_data.get('faculty')
        student_group = self.student_group

        if day_of_week and time_slot and faculty:
            # Check for faculty conflict
            faculty_conflict = Timetable.objects.filter(
                day_of_week=day_of_week,
                time_slot=time_slot,
                faculty=faculty
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if faculty_conflict.exists():
                raise forms.ValidationError(
                    f"{faculty.get_full_name()} is already scheduled for {day_of_week} at {time_slot}.")

            # Check for class conflict
            class_conflict = Timetable.objects.filter(
                day_of_week=day_of_week,
                time_slot=time_slot,
                student_group=student_group
            ).exclude(pk=self.instance.pk if self.instance.pk else None)

            if class_conflict.exists():
                raise forms.ValidationError(
                    f"{student_group.name} already has a class scheduled for {day_of_week} at {time_slot}.")

        return cleaned_data


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
        class_group_to_filter = None

        if is_faculty:
            self.fields['teacher'].widget = forms.HiddenInput()
            self.initial['teacher'] = self.user.pk
            self.fields['teacher'].queryset = User.objects.filter(pk=self.user.pk)
            teacher_to_filter = self.user
        else:  # Admin logic
            self.fields['teacher'].queryset = User.objects.filter(profile__role='faculty').order_by('first_name')

            # Get teacher from form data
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
                    pass

        # Get class group from form data
        class_group_id = None
        if self.is_bound and 'class_group' in self.data:
            class_group_id = self.data.get('class_group')
        elif 'class_group' in self.initial:
            class_group_id = self.initial.get('class_group')
        elif self.instance and self.instance.pk:
            class_group_id = self.instance.class_group_id

        if class_group_id:
            try:
                class_group_to_filter = StudentGroup.objects.get(pk=int(class_group_id))
            except (ValueError, TypeError, StudentGroup.DoesNotExist):
                pass

        # Filter subjects based on BOTH teacher AND class group
        if teacher_to_filter and class_group_to_filter:
            self.fields['subject'].queryset = CourseSubject.objects.filter(
                timetable_entries__faculty=teacher_to_filter,
                timetable_entries__student_group=class_group_to_filter
            ).select_related('subject', 'course').distinct().order_by('subject__name')

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


class SmtpSettingsForm(forms.ModelForm):
    class Meta:
        model = AttendanceSettings
        fields = [
            'email_host',
            'email_port',
            'email_host_user',
            'email_host_password',
            'email_use_tls',
            'email_use_ssl',
        ]
        widgets = {
            'email_host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., smtp.gmail.com'}),
            'email_port': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_host_user': forms.EmailInput(
                attrs={'class': 'form-control', 'placeholder': 'e.g., your-email@example.com'}),
            'email_host_password': forms.PasswordInput(
                attrs={'class': 'form-control', 'placeholder': 'Enter email or app password'}, render_value=True),
            'email_use_tls': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
            'email_use_ssl': forms.CheckboxInput(attrs={'class': 'custom-control-input'}),
        }


class BulkEmailForm(forms.Form):
    RECIPIENT_CHOICES = [
        ('all_students', 'All Students'),
        ('all_faculty', 'All Faculty'),
    ]

    # Get all student groups and add them to the choices
    # This uses a try-except block to prevent errors if the database isn't ready during migrations
    try:
        student_groups = [(f'group_{g.id}', g.name) for g in StudentGroup.objects.all()]
        RECIPIENT_CHOICES += student_groups
    except Exception:
        pass

    recipients = forms.MultipleChoiceField(
        choices=RECIPIENT_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        required=True,
        label="Recipients"
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=True
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        required=True,
        help_text="This message will be placed inside the standard email template."
    )


class AcademicSessionForm(forms.ModelForm):
    class Meta:
        model = AcademicSession
        fields = ['is_current']  # We only want to change the 'is_current' status

    # We can use a custom field to make it a dropdown list
    current_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        empty_label=None,  # No empty label
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class AcademicSessionModelForm(forms.ModelForm):
    class Meta:
        model = AcademicSession
        fields = ['name', 'start_year', 'end_year']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_year': forms.NumberInput(attrs={'class': 'form-control'}),
            'end_year': forms.NumberInput(attrs={'class': 'form-control'}),
        }
