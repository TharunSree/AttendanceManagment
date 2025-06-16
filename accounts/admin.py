from django.contrib import admin
from .models import Profile
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

# Define an inline admin descriptor for Profile model
# which acts a bit like a singleton
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'profile'

# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# We are un-registering the standalone Profile admin because it is now
# managed 'inline' with the User admin, which is a more intuitive workflow.
# You can uncomment the below if you want to manage Profiles separately.

# @admin.register(Profile)
# class ProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'role', 'student_id_number', 'contact_number')
#     search_fields = ('user__username', 'user__email', 'role')
#     list_filter = ('role',)