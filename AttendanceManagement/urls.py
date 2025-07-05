from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect


# This is your main project urls.py
def redirect_to_home(request):
    """Redirect root URL to accounts:home"""
    return redirect('accounts:home')


urlpatterns = [
    path('admin/', admin.site.urls),

    path('accounts/', include('accounts.urls')),
    path('academics/', include(('academics.urls', 'academics'), namespace='academics')),
    path('', redirect_to_home, name='root_redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
