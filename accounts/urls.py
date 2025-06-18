from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

from .forms import CustomPasswordResetForm, CustomSetPasswordForm

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name='accounts/password_reset_form.html',  # Template for the page showing the form
             email_template_name='registration/password_reset_email.txt',  # Plain text email template
             html_email_template_name='registration/password_reset_email.html',  # HTML email template
             form_class=CustomPasswordResetForm
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
             form_class=CustomSetPasswordForm
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    path('teachers/', views.teacher_list_view, name='teacher_list'),
    path('teachers/create/', views.teacher_create_view, name='teacher_create'),
    path('teachers/<int:pk>/delete/', views.teacher_delete_view, name='teacher_delete'),
    path('teachers/<int:pk>/update/', views.teacher_update_view, name='teacher_update'),
]
