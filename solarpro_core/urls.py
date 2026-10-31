from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    # Root redirect to login
    path('', RedirectView.as_view(url='/admin/login', permanent=False), name='root_redirect'),

    # Django built-in admin site
    path('django-admin/', admin.site.urls),

    # Web Modules
    path('', include('apps.authentication.urls')),
    path('', include('apps.masters.urls')),
    path('', include('apps.employees.urls')),
    path('', include('apps.operations.urls')),
    path('', include('apps.inventory.urls')),
    path('', include('apps.dynamic_forms.urls')),
    path('', include('apps.expenses.urls')),
    path('', include('apps.reports.urls')),

    # Mobile REST API
    path('api/', include('apps.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
