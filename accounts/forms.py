# accounts/forms.py
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm
from django import forms
from django.contrib.auth.models import User

from academics.models import Subject
from accounts.models import Profile


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control'})


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
