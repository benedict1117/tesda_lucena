from django.urls import path

from . import manage_views as m
from . import views

urlpatterns = [
    # Public / guest-visible pages (navigation bar)
    path("", views.home, name="home"),
    path("courses/", views.courses, name="courses"),
    path("training-centers/", views.training_centers, name="training_centers"),
    path("about/", views.about, name="about"),
    # Auth
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),
    # Trainee area (login required; guests are sent to the login page)
    path("dashboard/", views.dashboard, name="dashboard"),
    path("courses/<int:pk>/", views.course_detail, name="course_detail"),
    path("batches/", views.batches, name="batches"),
    path("enroll/<int:batch_id>/", views.enroll, name="enroll"),
    path("my-enrollment/", views.my_enrollment, name="my_enrollment"),
    path("my-enrollment/withdraw/", views.withdraw, name="withdraw"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read/", views.mark_all_read, name="notifications_read"),
    path("announcements/", views.announcements, name="announcements"),
    # Admin area
    path("manage/", m.dashboard, name="admin_dashboard"),
    path("manage/courses/", m.CourseList.as_view(), name="manage_courses"),
    path("manage/courses/add/", m.CourseCreate.as_view(), name="manage_course_add"),
    path("manage/courses/<int:pk>/edit/", m.CourseUpdate.as_view(), name="manage_course_edit"),
    path("manage/courses/<int:pk>/delete/", m.CourseDelete.as_view(), name="manage_course_delete"),
    path("manage/batches/", m.BatchList.as_view(), name="manage_batches"),
    path("manage/batches/add/", m.BatchCreate.as_view(), name="manage_batch_add"),
    path("manage/batches/<int:pk>/edit/", m.BatchUpdate.as_view(), name="manage_batch_edit"),
    path("manage/batches/<int:pk>/delete/", m.BatchDelete.as_view(), name="manage_batch_delete"),
    path("manage/centers/", m.CenterList.as_view(), name="manage_centers"),
    path("manage/centers/add/", m.CenterCreate.as_view(), name="manage_center_add"),
    path("manage/centers/<int:pk>/edit/", m.CenterUpdate.as_view(), name="manage_center_edit"),
    path("manage/centers/<int:pk>/delete/", m.CenterDelete.as_view(), name="manage_center_delete"),
    path("manage/enrollments/", m.EnrollmentList.as_view(), name="manage_enrollments"),
    path("manage/enrollments/add/", m.EnrollmentCreate.as_view(), name="manage_enrollment_add"),
    path("manage/enrollments/<int:pk>/edit/", m.EnrollmentUpdate.as_view(), name="manage_enrollment_edit"),
    path("manage/enrollments/<int:pk>/delete/", m.EnrollmentDelete.as_view(), name="manage_enrollment_delete"),
    path("manage/users/", m.UserList.as_view(), name="manage_users"),
    path("manage/users/<int:pk>/edit/", m.UserUpdate.as_view(), name="manage_user_edit"),
    path("manage/users/<int:pk>/delete/", m.UserDelete.as_view(), name="manage_user_delete"),
    path("manage/notifications/", m.AnnouncementList.as_view(), name="manage_announcements"),
    path("manage/notifications/add/", m.AnnouncementCreate.as_view(), name="manage_announcement_add"),
    path("manage/notifications/<int:pk>/edit/", m.AnnouncementUpdate.as_view(), name="manage_announcement_edit"),
    path("manage/notifications/<int:pk>/delete/", m.AnnouncementDelete.as_view(), name="manage_announcement_delete"),
    path("manage/reports/", m.reports, name="manage_reports"),
    path("manage/reports/enrollment.csv", m.report_csv, {"slug": "enrollment"}, name="manage_report_enrollment"),
    path("manage/reports/<slug:slug>.csv", m.report_csv, name="manage_report"),
    path("manage/settings/", m.settings_view, name="manage_settings"),
    path("manage/settings/backup/", m.backup, name="manage_backup"),
]
