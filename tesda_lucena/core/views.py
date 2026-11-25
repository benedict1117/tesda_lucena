"""Public pages and the trainee ("user") area."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import LogoutView as DjangoLogoutView
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import public_page, user_required
from .forms import LoginForm, RegisterForm
from .models import Announcement, Batch, Course, Enrollment, TrainingCenter


# ---------------------------------------------------------------- public pages


@public_page
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    featured = Course.objects.filter(is_active=True)[:6]
    return render(request, "home.html", {"featured": featured})


@public_page
def courses(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    qs = Course.objects.filter(is_active=True)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(category__icontains=q) | Q(nc_level__icontains=q))
    if category:
        qs = qs.filter(category=category)
    categories = Course.objects.filter(is_active=True).order_by("category").values_list("category", flat=True).distinct()
    return render(request, "courses.html", {"courses": qs, "q": q, "category": category, "categories": categories})


@public_page
def training_centers(request):
    # Rule: once logged in, the Training Centers link takes the trainee to Courses.
    if request.user.is_authenticated:
        return redirect("courses")
    centers = TrainingCenter.objects.filter(status="active")
    return render(request, "centers.html", {"centers": centers})


@public_page
def about(request):
    return render(request, "about.html")


# ----------------------------------------------------------------------- auth


class LoginView(DjangoLoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        nxt = self.get_redirect_url()
        # Only honour `next` when it belongs to the user's own area.
        if nxt and nxt.startswith("/manage/") == user.is_admin_role:
            return nxt
        return reverse("admin_dashboard" if user.is_admin_role else "dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session["notify_popup"] = True
        return response


@require_POST
def logout_view(request):
    return DjangoLogoutView.as_view()(request)


def register(request):
    if request.user.is_authenticated:
        return redirect("admin_dashboard" if request.user.is_admin_role else "dashboard")
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="core.backends.EmailOrPhoneBackend")
        request.session["notify_popup"] = True
        messages.success(request, "Your account has been created. Welcome to TESDA Lucena!")
        if (
            nxt
            and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()})
            and not nxt.startswith("/manage/")
        ):
            return redirect(nxt)
        return redirect("dashboard")
    return render(request, "auth/register.html", {"form": form, "next": nxt})


# ------------------------------------------------------------- trainee screens


@user_required
def dashboard(request):
    user = request.user
    enrollment = (
        user.enrollments.filter(status__in=Enrollment.ACTIVE)
        .select_related("batch__course", "batch__center")
        .first()
    )
    unread = user.notifications.filter(is_read=False).count()
    notify_count = unread if request.session.pop("notify_popup", False) else 0
    return render(
        request,
        "user/dashboard.html",
        {
            "enrollment": enrollment,
            "notifications": user.notifications.all()[:3],
            "announcement": Announcement.objects.first(),
            "notify_count": notify_count,
        },
    )


@user_required
def course_detail(request, pk):
    course = get_object_or_404(Course, pk=pk, is_active=True)
    batches = course.batches.select_related("center").exclude(status="closed")
    return render(request, "user/course_detail.html", {"course": course, "batches": batches})


@user_required
def batches(request):
    qs = Batch.objects.select_related("course", "center").exclude(status="closed")
    center = request.GET.get("center", "").strip()
    q = request.GET.get("q", "").strip()
    if center.isdigit():
        qs = qs.filter(center_id=center)
    if q:
        qs = qs.filter(Q(course__name__icontains=q) | Q(batch_no__icontains=q))
    return render(
        request,
        "user/batches.html",
        {
            "batches": qs,
            "centers": TrainingCenter.objects.filter(status="active"),
            "center": center,
            "q": q,
        },
    )


@user_required
def enroll(request, batch_id):
    batch = get_object_or_404(Batch.objects.select_related("course", "center"), pk=batch_id)
    if request.method != "POST":
        return redirect("course_detail", pk=batch.course_id)
    if not batch.is_open:
        messages.error(request, "This batch is no longer open for enrollment.")
    elif request.user.enrollments.filter(status__in=Enrollment.ACTIVE).exists():
        messages.error(
            request, "You already have an active enrollment. Withdraw from it first to join another batch."
        )
    else:
        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user, batch=batch, defaults={"status": Enrollment.PENDING}
        )
        if not created:  # re-enrolling after a withdrawal
            enrollment.status = Enrollment.PENDING
            enrollment.enrolled_on = timezone.localdate()
            enrollment.save()
        messages.success(request, "Your enrollment has been successfully submitted.")
        return redirect("my_enrollment")
    return redirect("course_detail", pk=batch.course_id)


@user_required
def my_enrollment(request):
    enrollment = (
        request.user.enrollments.filter(status__in=Enrollment.ACTIVE)
        .select_related("batch__course", "batch__center")
        .first()
    )
    history = request.user.enrollments.select_related("batch__course", "batch__center")
    return render(request, "user/enrollment.html", {"enrollment": enrollment, "history": history})


@require_POST
@user_required
def withdraw(request):
    enrollment = request.user.enrollments.filter(status__in=Enrollment.ACTIVE).first()
    if enrollment:
        enrollment.status = Enrollment.WITHDRAWN
        enrollment.save()
        messages.success(request, "Your enrollment has been successfully updated.")
    else:
        messages.error(request, "You have no active enrollment to withdraw from.")
    return redirect("dashboard")


@user_required
def notifications(request):
    page = Paginator(request.user.notifications.all(), 10).get_page(request.GET.get("page"))
    return render(request, "user/notifications.html", {"page_obj": page})


@require_POST
@user_required
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications")


@user_required
def announcements(request):
    page = Paginator(Announcement.objects.all(), 8).get_page(request.GET.get("page"))
    return render(request, "user/announcements.html", {"page_obj": page})
