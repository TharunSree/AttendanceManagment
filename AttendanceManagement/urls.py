from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# This is your main project urls.py

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- THIS IS THE FIX ---
    # Change the include() statements to use the recommended tuple format,
    # which provides an app_name and a namespace for URL discovery.
    
    # OLD WAY:
    # path('', include('accounts.urls')),
    # path('academics/', include('academics.urls')),

    # NEW, CORRECT WAY:
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('academics/', include(('academics.urls', 'academics'), namespace='academics')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)