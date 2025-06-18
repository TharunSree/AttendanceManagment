# accounts/forms.py
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django import forms
from django.contrib.auth.models import User

from academics.models import Subject
from accounts.models import Profile


class CustomPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'form-control'})

class CustomSetPasswordForm(SetPasswordForm): # Django's form for setting a new password
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control'})

class AddTeacherForm(forms.Form):
    # Fields from the User model
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)

    # Fields from the Profile model
    contact_number = forms.CharField(max_length=15, required=False,
                                     widget=forms.TextInput(attrs={'class': 'form-control'}))

    field_of_expertise = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        required=False,
        help_text="Select the subjects this teacher specializes in."
    )

    # Validation to prevent duplicate usernames or emails
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


class EditTeacherForm(forms.ModelForm):
    # We get these User fields to make them editable
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    # And these Profile fields
    field_of_expertise = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        required=False
    )

    class Meta:
        # The form is based on the Profile model, but we add User fields manually
        model = Profile
        fields = ['contact_number', 'field_of_expertise']
        widgets = {
            'contact_number': forms.TextInput(attrs={'class': 'form-control'}),
        }