# D:/AttendanceManagement/accounts/urls.py

# 1. Make sure to import reverse_lazy
from django.urls import path, include, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views

from .forms import CustomPasswordResetForm, CustomSetPasswordForm, CustomPasswordChangeForm

app_name = 'accounts'
urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- Password Reset Flow ---
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset_form.html',
             email_template_name='registration/password_reset_email.txt',
             html_email_template_name='registration/password_reset_email.html',
             form_class=CustomPasswordResetForm,
             # 2. Add this line to specify the namespaced success URL
             success_url=reverse_lazy('accounts:password_reset_done')
         ),
         name='password_reset'),

    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='accounts/password_reset_confirm.html',
             form_class=CustomSetPasswordForm,
             # 3. Add this line here as well for the next step in the flow
             success_url=reverse_lazy('accounts:password_reset_complete')
         ),
         name='password_reset_confirm'),

    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change_form.html',
        form_class=CustomPasswordChangeForm,
        success_url='/accounts/password_change/done/'  # Use the built-in success page
    ), name='password_change'),

    # --- Other App URLs ---
    path('teachers/', views.teacher_list_view, name='teacher_list'),
    path('teachers/create/', views.teacher_create_view, name='teacher_create'),
    path('teachers/<int:pk>/delete/', views.teacher_delete_view, name='teacher_delete'),
    path('teachers/<int:pk>/update/', views.teacher_update_view, name='teacher_update'),
    path('groups/', views.group_permission_list_view, name='group_permission_list'),
    path('groups/<int:group_id>/edit/', views.group_permission_edit_view, name='group_permission_edit'),
    path('dashboard/admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('dashboard/faculty/', views.faculty_dashboard_view, name='faculty_dashboard'),
    path('dashboard/student/', views.student_dashboard_view, name='student_dashboard'),
    path('user/<int:user_id>/trigger-password-reset/', views.admin_trigger_password_reset_view,
         name='admin_trigger_password_reset'),
    path('account/', views.account_view, name='account_view'),
    path('users/bulk-import/', views.bulk_user_import_view, name='bulk_user_import'),
    path('users/bulk-import/template/', views.download_csv_template_view, name='download_csv_template'),
    path('notifications/mark-as-read/', views.mark_notifications_as_read_view, name='mark_notifications_as_read'),


    # See code quality suggestion below
    path('', include('django.contrib.auth.urls')),

]
