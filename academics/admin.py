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
    TimeSlot,
    ClassCancellation, Mark, User
)


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_year', 'end_year', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('name', 'start_year')
    ordering = ('-start_year',)


class CourseSubjectInline(admin.TabularInline):
    model = CourseSubject
    extra = 1  # How many empty rows to show


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_type', 'duration_years')
    search_fields = ('name',)

    # This will now display a table on the course page to add/edit subjects by semester
    inlines = [CourseSubjectInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'start_year', 'passout_year')
    search_fields = ('name', 'course__name')
    list_filter = ('course',)
    # Makes adding students easier


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


@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'criterion', 'marks_obtained', 'get_max_marks')
    list_filter = ('subject__semester', 'criterion', 'subject__subject')
    search_fields = ('student__first_name', 'student__last_name', 'student__username', 'subject__subject__name')
    autocomplete_fields = ['student']
    readonly_fields = ('get_max_marks',)

    fieldsets = (
        (None, {
            'fields': ('student', 'subject', 'criterion', 'marks_obtained', 'get_max_marks')
        }),
    )

    def get_max_marks(self, obj):
        """Display the maximum marks for the criterion"""
        return obj.criterion.max_marks if obj.criterion else 'N/A'

    get_max_marks.short_description = 'Max Marks'

    def get_queryset(self, request):
        """Optimize queries by selecting related objects"""
        return super().get_queryset(request).select_related(
            'student', 'subject__subject', 'criterion'
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize the foreign key fields"""
        if db_field.name == "student":
            kwargs["queryset"] = User.objects.filter(profile__role='student').order_by('first_name', 'last_name')
        elif db_field.name == "subject":
            kwargs["queryset"] = CourseSubject.objects.select_related('subject').order_by('subject__name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# You can also register your other models if you want to manage them here
admin.site.register(AttendanceRecord)
admin.site.register(CourseSubject)
admin.site.register(TimeSlot)
admin.site.register(ClassCancellation)
