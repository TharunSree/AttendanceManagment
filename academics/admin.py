from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import (
    AcademicSession,
    Course,
    Subject,
    StudentGroup,
    AttendanceSettings,
    Timetable,
    AttendanceRecord,
    CourseSubject,
    TimeSlot
)


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_year', 'end_year', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('name', 'start_year')
    ordering = ('-start_year',)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_type', 'duration_years')
    search_fields = ('name',)
    filter_horizontal = ('subjects',)  # Provides a nice interface for ManyToManyFields


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'start_year', 'passout_year')
    search_fields = ('name', 'course__name')
    list_filter = ('course',)
    filter_horizontal = ('students',)  # Makes adding students easier


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    # This setup prevents adding new settings and redirects to the existing one
    def changelist_view(self, request, extra_context=None):
        settings_obj, created = AttendanceSettings.objects.get_or_create(pk=1)
        return HttpResponseRedirect(reverse(
            'admin:academics_attendancesettings_change',
            args=[settings_obj.pk]
        ))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('student_group', 'subject', 'faculty', 'day_of_week', 'time_slot')
    list_filter = ('student_group', 'faculty', 'day_of_week')


# You can also register your other models if you want to manage them here
admin.site.register(AttendanceRecord)
admin.site.register(CourseSubject)
admin.site.register(TimeSlot)
