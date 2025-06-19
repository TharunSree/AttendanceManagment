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

    # --- Academic Session Management URLs ---

]
