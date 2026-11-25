from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Announcement, Batch, Course, Enrollment, Notification, SiteSetting, TrainingCenter, User


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("TESDA", {"fields": ("role", "phone")}),)
    list_display = ("username", "email", "phone", "role", "is_active")
    list_filter = ("role", "is_active")


for model in (Course, TrainingCenter, Batch, Enrollment, Announcement, Notification, SiteSetting):
    admin.site.register(model)
