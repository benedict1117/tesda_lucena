from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django's built-in admin is kept for developers only; the TESDA admin UI lives at /manage/
    path("django-admin/", admin.site.urls),
    path("", include("core.urls")),
]
