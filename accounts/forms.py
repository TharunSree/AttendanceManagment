# accounts/forms.py
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm
from django import forms
from django.contrib.auth.models import User
from django.template.loader import render_to_string

from academics.email_utils import send_database_email
from academics.models import Subject
from accounts.models import Profile
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.templatetags.static import static


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control'})

    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        """
        This method overrides the default to send an email using our custom utility,
        which pulls SMTP settings from the database.
        """
        # Render the subject from the template
        request = context.get('request')
        subject = render_to_string(subject_template_name, context).strip()

        # Use HTML template if provided, otherwise fall back to text
        if html_email_template_name:
            if request:
                context['logo_url'] = request.build_absolute_uri(static('logos/mobile.svg'))
            else:
                # Fallback if no request available
                context['logo_url'] = static('logos/mobile.svg')
            body = render_to_string(html_email_template_name, context)
            # For HTML emails, you might want to add content_type parameter
            send_database_email(
                subject=subject,
                body=body,
                recipient_list=[to_email],
                html_message=body  # Pass as HTML content
            )
        else:
            # Fallback to text template
            body = render_to_string(email_template_name, context)
            send_database_email(
                subject=subject,
                body=body,
                recipient_list=[to_email]
            )


class CustomSetPasswordForm(SetPasswordForm):  # Django's form for setting a new password
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})


class AddTeacherForm(forms.Form):
    # ... (username, first_name, last_name, email, password fields)
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    # --- ADD PHOTO FIELD HERE ---
    photo = forms.ImageField(required=False)
    # --------------------------

    contact_number = forms.CharField(max_length=15, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))

    field_of_expertise = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        required=False,
        help_text="Select the subjects this teacher specializes in."
    )
    # ... (validation methods remain the same)


class EditTeacherForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    field_of_expertise = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        required=False
    )

    class Meta:
        model = Profile
        # --- ADD 'photo' TO THE FIELDS LIST ---
        fields = ['photo', 'contact_number', 'field_of_expertise']
        # ------------------------------------
        widgets = {
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
            # Note: We will style the photo field in the template, so no widget is needed here.
        }


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
        }


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['contact_number']
        widgets = {
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Number'}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Current Password'})
        self.fields['new_password1'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'New Password'})
        self.fields['new_password2'].widget = forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'})


class BulkImportForm(forms.Form):
    file = forms.FileField(widget=forms.FileInput(attrs={'class': 'custom-file-input'}))
