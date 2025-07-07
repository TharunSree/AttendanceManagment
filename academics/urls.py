from django.urls import path
from . import views

# This is a good practice for namespacing your URLs
app_name = 'academics'

urlpatterns = [
    # --- Course Management URLs ---
    path('courses/', views.course_list_view, name='course_list'),
    path('courses/create/', views.course_create_view, name='course_create'),
    path('courses/<int:pk>/update/', views.course_update_view, name='course_update'),
    path('courses/<int:pk>/delete/', views.course_delete_view, name='course_delete'),

    # --- Class (StudentGroup) Management URLs ---
    path('class/create/', views.student_group_create_view, name='student_group_create'),
    path('class/<int:pk>/update/', views.student_group_update_view, name='student_group_update'),
    path('class/<int:pk>/delete/', views.student_group_delete_view, name='student_group_delete'),

    # --- Student Management URLs ---
    path('class/<int:group_id>/add-student/', views.student_create_view, name='student_create'),
    path('student/<int:pk>/delete/', views.student_delete_view, name='student_delete'),

    # --- Admin Attendance Viewing Flow URLs ---
    path('attendance-view/select-class/', views.admin_select_class_view, name='admin_select_class'),
    path('attendance-view/class/<int:group_id>/', views.admin_student_list_view, name='admin_student_list'),
    path('attendance-view/student/<int:student_id>/', views.admin_student_attendance_detail_view,
         name='admin_student_attendance_detail'),
    path('subjects/', views.subject_list_view, name='subject_list'),
    path('subjects/create/', views.subject_create_view, name='subject_create'),
    path('subjects/<int:pk>/update/', views.subject_update_view, name='subject_update'),
    path('subjects/<int:pk>/delete/', views.subject_delete_view, name='subject_delete'),
    path('student/<int:pk>/update/', views.student_update_view, name='student_update'),
    path('coming-soon/', views.faculty_daily_schedule_view, name='coming_soon'),
    path('settings/', views.admin_settings_view, name='admin_settings'),
    path('settings/timeslot/<int:pk>/delete/', views.timeslot_delete_view, name='timeslot_delete'),
    path('faculty/schedule/', views.faculty_daily_schedule_view, name='faculty_schedule'),
    path('faculty/mark-attendance/<int:timetable_id>/', views.mark_attendance_view, name='mark_attendance'),
    path('faculty/mark-attendance/<int:timetable_id>/<str:date_str>', views.mark_attendance_view,
         name='mark_attendance_for_date'),
    path('faculty/cancel-class/<int:timetable_id>/', views.class_cancellation_view, name='cancel_class'),
    path('faculty/previous-attendance/', views.previous_attendance_view, name='previous_attendance'),
    path('daily-log/', views.daily_attendance_log_view, name='daily_log'),
    path('daily-log/<int:timetable_id>/<str:date>/', views.daily_log_detail_view, name='daily_log_detail'),
    path('daily-log/extra-class/<int:extra_class_id>/<str:date>/', views.extra_class_log_detail_view,
         name='extra_class_log_detail'),
    path('timetable-entry/create/<int:group_id>/<str:day>/<int:timeslot_id>/', views.timetable_entry_create_view,
         name='timetable_entry_create'),
    path('timetable-entry/update/<int:entry_id>/', views.timetable_entry_update_view, name='timetable_entry_update'),
    path('timetable-entry/delete/<int:entry_id>/', views.timetable_entry_delete_view, name='timetable_entry_delete'),
    path('manage_timetable/', views.manage_timetable_view, name='manage_timetable'),
    path('manage-substitutions/', views.manage_substitutions_view, name='manage_substitutions'),
    path('assign-substitution/<int:timetable_id>/', views.assign_substitution_view, name='assign_substitution'),
    path('cancel-substitution/<int:timetable_id>/', views.cancel_substitution_view, name='cancel_substitution'),
    path('student/my-attendance/', views.student_my_attendance_view, name='student_my_attendance'),
    path('student/my-timetable/', views.student_timetable_view, name='student_timetable'),
    path('reports/attendance/', views.attendance_report_view, name='attendance_report'),
    path('reports/attendance/download/', views.download_attendance_report_view, name='download_attendance_report'),
    path('announcements/', views.announcement_list_view, name='announcement_list'),
    path('announcements/create/', views.announcement_create_view, name='announcement_create'),
    path('api/check-announcements/', views.check_announcements_view, name='check_announcements'),
    path('search/', views.global_search_view, name='global_search'),
    path('late-comers/', views.late_comers_view, name='late_comers'),
    path('student/<int:student_id>/profile/', views.student_profile_view, name='student_profile'),
    path('schemes/', views.scheme_list_view, name='scheme_list'),
    path('schemes/add/', views.scheme_create_view, name='scheme_create'),
    path('schemes/<int:pk>/edit/', views.scheme_update_view, name='scheme_update'),
    path('schemes/<int:pk>/delete/', views.scheme_delete_view, name='scheme_delete'),
    path('marks/entry/', views.marks_entry_view, name='marks_entry'),
    path('marks/import/', views.bulk_marks_import_view, name='bulk_marks_import'),
    path('marks/import/template/', views.download_marks_template_view, name='download_marks_template'),
    path('my-marks/', views.student_my_marks_view, name='student_my_marks'),
    path('reports/marks/', views.marks_report_view, name='marks_report'),
    path('reports/marks/download/', views.download_marks_report_view, name='download_marks_report'),
    path('my-profile/', views.my_profile_view, name='my_profile'),
    path('extra-class/schedule/', views.schedule_extra_class, name='schedule_extra_class'),
    path('extra-class/list/', views.extra_class_list, name='extra_class_list'),
    path('extra-class/update/<int:pk>/', views.extra_class_update, name='extra_class_update'),
    path('extra-class/delete/<int:pk>/', views.extra_class_delete, name='extra_class_delete'),
    path('attendance/extra-class/<int:extra_class_id>/', views.mark_extra_class_attendance_view,
         name='mark_extra_class_attendance'),
    path('student/<int:student_id>/report/pdf/', views.student_report_card_pdf_view, name='student_report_pdf'),

    # The URL that Pyppeteer will visit internally to render the HTML
    path('student/<int:student_id>/report/html/', views.student_report_card_html_view, name='student_report_html'),
    path('guide/', views.guide_view, name='guide'),
    path('ajax/teacher-class-subjects/', views.get_teacher_class_subjects_view, name='get_teacher_class_subjects'),
    path('ajax/subject-faculty/', views.get_subject_faculty_view, name='get_subject_faculty'),
    path('backup-restore/', views.backup_restore_view, name='backup_restore'),
    path('settings/smtp/', views.smtp_settings_view, name='smtp_settings'),
    path('reports/', views.system_reports_view, name='system_reports'),
    path('update-status/', views.update_status_view, name='update_status'),
    path('bulk-email/', views.bulk_email_view, name='bulk_email'),
    path('publish-results/', views.publish_results_view, name='publish_results'),
    path('publish-results/send/<int:student_id>/<int:group_id>/<int:semester>/', views.send_parent_report_email_view,
         name='send_parent_report'),
    path('publish-results/bulk/<int:group_id>/<int:semester>/', views.bulk_publish_results_view,
         name='bulk_publish_results'),

    # --- Academic Session Management URLs ---

]
