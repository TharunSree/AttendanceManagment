from django.contrib import admin
from .models import Profile  # Import your Profile model

# Register your models here.

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'get_username', 'get_email')  # Fields to display in the admin list
    search_fields = ('user__username', 'user__email', 'role')    # Fields to search by
    list_filter = ('role',)  # Fields to filter by in the sidebar

    @admin.display(ordering='user__username', description='Username')
    def get_username(self, obj):
        return obj.user.username

    @admin.display(ordering='user__email', description='Email')
    def get_email(self, obj):
        return obj.user.email

admin.site.register(Profile, ProfileAdmin)