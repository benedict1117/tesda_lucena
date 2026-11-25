"""Admin area (/manage/...). Every view here is admin-only."""

import csv
from collections import Counter
from io import StringIO

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.management import call_command
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .decorators import admin_required
from .forms import (
    AnnouncementForm,
    BatchForm,
    CourseForm,
    EnrollmentForm,
    GeneralSettingsForm,
    NotificationSettingsForm,
    TrainingCenterForm,
    UserEditForm,
)
from .models import Announcement, Batch, Course, Enrollment, Notification, SiteSetting, TrainingCenter

User = get_user_model()


def fmt_date(d):
    return d.strftime("%b %d, %Y") if d else ""


def resolve(obj, path):
    if callable(path):
        return path(obj)
    for part in path.split("."):
        obj = getattr(obj, part)
        if callable(obj):
            obj = obj()
    return obj


# ----------------------------------------------------------------- base mixins


class AdminOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_admin_role

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        return redirect("dashboard")  # a trainee tried to open an admin page


class ManageList(AdminOnlyMixin, ListView):
    template_name = "manage/list.html"
    paginate_by = 5
    active = ""
    prefix = ""  # url prefix: manage_<prefix>_add / _edit / _delete
    list_url_name = ""
    title = subtitle = add_label = ""
    columns = []  # (header, attribute-path-or-callable, mode)  mode: None | "status" | "nc"
    search_fields = []
    can_add = can_edit = can_delete = True
    export_url_name = None

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(cond)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        page = ctx["page_obj"]
        rows = []
        for number, obj in enumerate(page.object_list, start=page.start_index()):
            cells = []
            for _header, path, mode in self.columns:
                value = resolve(obj, path)
                badge = slugify(str(value)) if mode == "status" else ("nc" if mode == "nc" else None)
                cells.append({"value": value, "badge": badge})
            rows.append(
                {
                    "number": number,
                    "cells": cells,
                    "edit_url": reverse(f"manage_{self.prefix}_edit", args=[obj.pk]) if self.can_edit else None,
                    "delete_url": reverse(f"manage_{self.prefix}_delete", args=[obj.pk]) if self.can_delete else None,
                }
            )
        ctx.update(
            active=self.active,
            title=self.title,
            subtitle=self.subtitle,
            add_label=self.add_label,
            add_url=reverse(f"manage_{self.prefix}_add") if self.can_add else None,
            export_url=reverse(self.export_url_name) if self.export_url_name else None,
            headers=[c[0] for c in self.columns],
            rows=rows,
            q=self.request.GET.get("q", ""),
            search_action=reverse(self.list_url_name),
        )
        return ctx


class ManageFormMixin(AdminOnlyMixin):
    template_name = "manage/form.html"
    active = ""
    list_url_name = ""
    noun = ""

    def get_success_url(self):
        return reverse(self.list_url_name)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        creating = getattr(self, "object", None) is None or self.object.pk is None
        ctx.update(
            active=self.active,
            title=f"{'Add' if creating else 'Edit'} {self.noun}",
            back_url=reverse(self.list_url_name),
            search_action=reverse(self.list_url_name),
        )
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"{self.noun} saved successfully.")
        return response


class ManageCreate(ManageFormMixin, CreateView):
    pass


class ManageUpdate(ManageFormMixin, UpdateView):
    pass


class ManageDelete(AdminOnlyMixin, View):
    model = None
    list_url_name = ""
    noun = ""

    def get(self, request, pk):
        return redirect(self.list_url_name)

    def guard(self, request, obj):
        return None  # return an error string to block deletion

    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        problem = self.guard(request, obj)
        if problem:
            messages.error(request, problem)
            return redirect(self.list_url_name)
        try:
            obj.delete()
            messages.success(request, f"{self.noun} deleted.")
        except ProtectedError:
            messages.error(request, f"This {self.noun.lower()} is still in use and cannot be deleted.")
        return redirect(self.list_url_name)


# --------------------------------------------------------------------- courses


class CourseList(ManageList):
    model = Course
    active, prefix, list_url_name = "courses", "course", "manage_courses"
    title, subtitle, add_label = "Course Management", "Manage TESDA courses and qualifications", "Add Course"
    columns = [("Course Name", "name", None), ("NC Level", "nc_level", "nc"), ("Category", "category", None)]
    search_fields = ["name", "category", "nc_level"]


class CourseCreate(ManageCreate):
    model, form_class = Course, CourseForm
    active, list_url_name, noun = "courses", "manage_courses", "Course"


class CourseUpdate(ManageUpdate):
    model, form_class = Course, CourseForm
    active, list_url_name, noun = "courses", "manage_courses", "Course"


class CourseDelete(ManageDelete):
    model, list_url_name, noun = Course, "manage_courses", "Course"


# --------------------------------------------------------------------- batches


class BatchList(ManageList):
    model = Batch
    active, prefix, list_url_name = "batches", "batch", "manage_batches"
    title, subtitle, add_label = "Batch Availability", "Manage training batches and availability", "Add Batch"
    queryset = Batch.objects.select_related("course", "center")
    columns = [
        ("Course", "course.name", None),
        ("Training Center", "center.name", None),
        ("Batch No.", "batch_no", None),
        ("Start Date", lambda o: fmt_date(o.start_date), None),
        ("End Date", lambda o: fmt_date(o.end_date), None),
        ("Slots", "slots_left", None),
        ("Status", "get_status_display", "status"),
    ]
    search_fields = ["course__name", "center__name", "batch_no"]


class BatchCreate(ManageCreate):
    model, form_class = Batch, BatchForm
    active, list_url_name, noun = "batches", "manage_batches", "Batch"


class BatchUpdate(ManageUpdate):
    model, form_class = Batch, BatchForm
    active, list_url_name, noun = "batches", "manage_batches", "Batch"


class BatchDelete(ManageDelete):
    model, list_url_name, noun = Batch, "manage_batches", "Batch"


# ------------------------------------------------------------ training centers


class CenterList(ManageList):
    model = TrainingCenter
    active, prefix, list_url_name = "centers", "center", "manage_centers"
    title, subtitle, add_label = "Training Centers", "Manage TESDA training centers in Lucena City", "Add Center"
    columns = [
        ("Center Name", "name", None),
        ("Address", "address", None),
        ("Contact", "contact", None),
        ("Programs Offered", "programs_offered", None),
        ("Status", "get_status_display", "status"),
    ]
    search_fields = ["name", "address", "programs_offered"]


class CenterCreate(ManageCreate):
    model, form_class = TrainingCenter, TrainingCenterForm
    active, list_url_name, noun = "centers", "manage_centers", "Training center"


class CenterUpdate(ManageUpdate):
    model, form_class = TrainingCenter, TrainingCenterForm
    active, list_url_name, noun = "centers", "manage_centers", "Training center"


class CenterDelete(ManageDelete):
    model, list_url_name, noun = TrainingCenter, "manage_centers", "Training center"


# ----------------------------------------------------------------- enrollments


class EnrollmentList(ManageList):
    model = Enrollment
    active, prefix, list_url_name = "enrollments", "enrollment", "manage_enrollments"
    title, subtitle, add_label = "Enrollment Records", "View and manage student enrollments", "Add Enrollment"
    queryset = Enrollment.objects.select_related("user", "batch__course", "batch__center")
    export_url_name = "manage_report_enrollment"
    columns = [
        ("Student Name", lambda o: o.user.full_display_name, None),
        ("Course", "batch.course.name", None),
        ("Training Center", "batch.center.name", None),
        ("Batch", "batch.batch_no", None),
        ("Enrollment Date", lambda o: fmt_date(o.enrolled_on), None),
        ("Status", "get_status_display", "status"),
    ]
    search_fields = ["user__first_name", "user__last_name", "batch__course__name", "batch__batch_no"]


class EnrollmentCreate(ManageCreate):
    model, form_class = Enrollment, EnrollmentForm
    active, list_url_name, noun = "enrollments", "manage_enrollments", "Enrollment"


class EnrollmentUpdate(ManageUpdate):
    model, form_class = Enrollment, EnrollmentForm
    active, list_url_name, noun = "enrollments", "manage_enrollments", "Enrollment"


class EnrollmentDelete(ManageDelete):
    model, list_url_name, noun = Enrollment, "manage_enrollments", "Enrollment"


# ----------------------------------------------------------------------- users


class UserList(ManageList):
    model = User
    active, prefix, list_url_name = "users", "user", "manage_users"
    title, subtitle = "Users", "Manage trainee and admin accounts"
    can_add = False
    columns = [
        ("Name", lambda o: o.full_display_name, None),
        ("Email", lambda o: o.email or "—", None),
        ("Mobile", lambda o: o.phone or "—", None),
        ("Role", "get_role_display", "status"),
        ("Status", lambda o: "Active" if o.is_active else "Inactive", "status"),
    ]
    search_fields = ["first_name", "last_name", "email", "phone"]

    def get_queryset(self):
        return super().get_queryset().order_by("role", "first_name", "username")


class UserUpdate(ManageUpdate):
    model, form_class = User, UserEditForm
    active, list_url_name, noun = "users", "manage_users", "User"


class UserDelete(ManageDelete):
    model, list_url_name, noun = User, "manage_users", "User"

    def guard(self, request, obj):
        if obj.pk == request.user.pk:
            return "You cannot delete your own account."
        if Enrollment.objects.filter(user=obj).exists():
            return "This user has enrollment records. Set the account to inactive instead."
        return None


# --------------------------------------------------------------- announcements


class AnnouncementList(ManageList):
    model = Announcement
    active, prefix, list_url_name = "notifications", "announcement", "manage_announcements"
    title, subtitle, add_label = "Notifications", "Post announcements that every trainee receives", "New Announcement"
    columns = [
        ("Title", "title", None),
        ("Event Date", lambda o: fmt_date(o.event_date) or "—", None),
        ("Posted", lambda o: fmt_date(o.created_at), None),
    ]
    search_fields = ["title", "body"]


class AnnouncementCreate(ManageCreate):
    model, form_class = Announcement, AnnouncementForm
    active, list_url_name, noun = "notifications", "manage_announcements", "Announcement"

    def form_valid(self, form):
        response = super().form_valid(form)
        users = User.objects.filter(role=User.ROLE_USER, is_active=True)
        Notification.objects.bulk_create(
            [
                Notification(
                    user=u,
                    kind=Notification.ANNOUNCEMENT,
                    title=self.object.title,
                    message=self.object.body[:200],
                )
                for u in users
            ]
        )
        return response


class AnnouncementUpdate(ManageUpdate):
    model, form_class = Announcement, AnnouncementForm
    active, list_url_name, noun = "notifications", "manage_announcements", "Announcement"


class AnnouncementDelete(ManageDelete):
    model, list_url_name, noun = Announcement, "manage_announcements", "Announcement"


# ------------------------------------------------------------------- dashboard


@admin_required
def dashboard(request):
    stats = [
        ("Courses", Course.objects.count(), "bi-book"),
        ("Open Batches", Batch.objects.filter(status__in=["available", "upcoming"]).count(), "bi-calendar3"),
        ("Training Centers", TrainingCenter.objects.count(), "bi-bank"),
        ("Enrollments", Enrollment.objects.exclude(status="withdrawn").count(), "bi-people"),
        ("Pending Approval", Enrollment.objects.filter(status="pending").count(), "bi-hourglass-split"),
        ("Trainee Accounts", User.objects.filter(role="user").count(), "bi-person-check"),
    ]
    recent = Enrollment.objects.select_related("user", "batch__course", "batch__center")[:5]
    return render(
        request,
        "manage/dashboard.html",
        {
            "active": "dashboard",
            "stats": stats,
            "recent": recent,
            "search_action": reverse("manage_courses"),
        },
    )


# --------------------------------------------------------------------- reports

REPORTS = [
    ("enrollment", "Enrollment Report", "View total enrollments by course and period", "bi-graph-up"),
    ("course-availability", "Course Availability Report", "Check available courses and batches", "bi-calendar3"),
    ("batch", "Batch Report", "View batch details and status", "bi-file-earmark-text"),
    ("training-center", "Training Center Report", "View center statistics", "bi-bank"),
    ("monthly", "Monthly Summary", "Enrollment summary per month", "bi-pie-chart"),
]


@admin_required
def reports(request):
    return render(
        request,
        "manage/reports.html",
        {
            "active": "reports",
            "reports": REPORTS,
            "search_action": reverse("manage_courses"),
        },
    )


def _report_rows(slug):
    if slug == "enrollment":
        header = ["Student", "Course", "Training Center", "Batch", "Enrollment Date", "Status"]
        qs = Enrollment.objects.select_related("user", "batch__course", "batch__center")
        rows = [
            [e.user.full_display_name, e.batch.course.full_name, e.batch.center.name, e.batch.batch_no,
             e.enrolled_on.isoformat(), e.get_status_display()]
            for e in qs
        ]
    elif slug == "course-availability":
        header = ["Course", "NC Level", "Category", "Open Batches", "Slots Left"]
        rows = []
        for c in Course.objects.filter(is_active=True):
            open_batches = [b for b in c.batches.all() if b.is_open]
            rows.append([c.name, c.nc_level, c.category, len(open_batches), sum(b.slots_left for b in open_batches)])
    elif slug == "batch":
        header = ["Batch No.", "Course", "Training Center", "Start", "End", "Slots", "Enrolled", "Status"]
        rows = [
            [b.batch_no, b.course.full_name, b.center.name, b.start_date.isoformat(), b.end_date.isoformat(),
             b.slots, b.taken_slots, b.get_status_display()]
            for b in Batch.objects.select_related("course", "center")
        ]
    elif slug == "training-center":
        header = ["Center", "Address", "Status", "Batches", "Active Enrollments"]
        rows = [
            [c.name, c.address, c.get_status_display(), c.batches.count(),
             Enrollment.objects.filter(batch__center=c).exclude(status="withdrawn").count()]
            for c in TrainingCenter.objects.all()
        ]
    elif slug == "monthly":
        header = ["Month", "Enrollments"]
        counts = Counter(e.enrolled_on.strftime("%Y-%m") for e in Enrollment.objects.exclude(status="withdrawn"))
        rows = [[m, counts[m]] for m in sorted(counts)]
    else:
        raise Http404
    return header, rows


@admin_required
def report_csv(request, slug):
    header, rows = _report_rows(slug)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="tesda-{slug}-{timezone.localdate()}.csv"'
    response.write("﻿")  # BOM so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


# -------------------------------------------------------------------- settings


@admin_required
def settings_view(request):
    tab = request.GET.get("tab", "general")
    setting = SiteSetting.load()
    form_classes = {"general": GeneralSettingsForm, "notifications": NotificationSettingsForm}
    form = None
    if tab in form_classes:
        form = form_classes[tab](request.POST or None, instance=setting)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Settings saved successfully.")
            return redirect(f"{reverse('manage_settings')}?tab={tab}")
    return render(
        request,
        "manage/settings.html",
        {"active": "settings", "tab": tab, "form": form, "search_action": reverse("manage_courses")},
    )


@admin_required
def backup(request):
    buffer = StringIO()
    call_command("dumpdata", "core", indent=2, natural_foreign=True, stdout=buffer)
    response = HttpResponse(buffer.getvalue(), content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="tesda-backup-{timezone.localdate()}.json"'
    return response
