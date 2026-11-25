from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Single user table; `role` separates trainees ("user") from staff ("admin")."""

    ROLE_USER = "user"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [(ROLE_USER, "User"), (ROLE_ADMIN, "Admin")]

    email = models.EmailField("email address", unique=True, null=True, blank=True)
    phone = models.CharField("mobile number", max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_USER)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ROLE_ADMIN
        # Unique + nullable columns must store NULL, never "".
        self.email = self.email or None
        self.phone = self.phone or None
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.ROLE_ADMIN

    @property
    def display_name(self) -> str:
        return self.first_name or self.email or self.phone or self.username

    @property
    def full_display_name(self) -> str:
        full = self.get_full_name().strip()
        return full or self.display_name


class Course(models.Model):
    NC_CHOICES = [(c, c) for c in ("NC I", "NC II", "NC III", "NC IV")]

    name = models.CharField(max_length=150)
    nc_level = models.CharField(max_length=10, choices=NC_CHOICES, default="NC II")
    category = models.CharField(max_length=80, help_text="e.g. TVET, ICT, Health Care")
    description = models.TextField(blank=True)
    duration_hours = models.PositiveIntegerField(default=0)
    provider = models.CharField(
        max_length=150, default="Technical Education and Skills Development Authority (TESDA)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} {self.nc_level}"

    @property
    def full_name(self):
        return f"{self.name} {self.nc_level}"


class TrainingCenter(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255)
    contact = models.CharField(max_length=60, blank=True)
    programs_offered = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def map_bbox(self):
        if self.latitude is None or self.longitude is None:
            return ""
        d_lng, d_lat = 0.01, 0.006
        return f"{self.longitude - d_lng},{self.latitude - d_lat},{self.longitude + d_lng},{self.latitude + d_lat}"


class Batch(models.Model):
    STATUS_CHOICES = [
        ("available", "Available"),
        ("upcoming", "Upcoming"),
        ("ongoing", "Ongoing"),
        ("closed", "Closed"),
    ]

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="batches")
    center = models.ForeignKey(TrainingCenter, on_delete=models.PROTECT, related_name="batches")
    batch_no = models.CharField(max_length=30, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    schedule_time = models.CharField(max_length=60, default="8:00 AM – 5:00 PM")
    slots = models.PositiveIntegerField(default=25)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="available")

    class Meta:
        ordering = ["start_date", "batch_no"]
        verbose_name_plural = "batches"

    def __str__(self):
        return f"{self.batch_no} – {self.course}"

    @property
    def taken_slots(self):
        return self.enrollments.exclude(status="withdrawn").count()

    @property
    def slots_left(self):
        return max(self.slots - self.taken_slots, 0)

    @property
    def is_open(self):
        return self.status in ("available", "upcoming") and self.slots_left > 0

    @property
    def schedule_label(self):
        return (
            f"{self.start_date:%b %d} – {self.end_date:%b %d, %Y} • {self.schedule_time}"
        )

    def save(self, *args, **kwargs):
        old = None
        if self.pk:
            old = Batch.objects.filter(pk=self.pk).values(
                "start_date", "end_date", "schedule_time", "center_id"
            ).first()
        super().save(*args, **kwargs)
        changed = old and (
            old["start_date"] != self.start_date
            or old["end_date"] != self.end_date
            or old["schedule_time"] != self.schedule_time
            or old["center_id"] != self.center_id
        )
        if changed:
            user_ids = self.enrollments.exclude(status="withdrawn").values_list("user_id", flat=True)
            Notification.objects.bulk_create(
                [
                    Notification(
                        user_id=uid,
                        kind=Notification.SCHEDULE,
                        title="Schedule Update",
                        message="Training schedule has been updated. Please check your dashboard.",
                    )
                    for uid in user_ids
                ]
            )


class Enrollment(models.Model):
    PENDING, ENROLLED, WITHDRAWN = "pending", "enrolled", "withdrawn"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (ENROLLED, "Enrolled"),
        (WITHDRAWN, "Withdrawn"),
    ]
    ACTIVE = (PENDING, ENROLLED)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="enrollments")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    enrolled_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "batch"], name="uniq_user_batch"),
        ]

    def __str__(self):
        return f"{self.user} → {self.batch}"

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = Enrollment.objects.filter(pk=self.pk).values_list("status", flat=True).first()
        super().save(*args, **kwargs)
        if previous == self.status:
            return
        course = self.batch.course.name
        texts = {
            self.PENDING: (
                "Enrollment Received",
                f"Your enrollment for {course} has been received and is awaiting confirmation.",
            ),
            self.ENROLLED: (
                "Enrollment Confirmed",
                f"Your enrollment for {course} has been confirmed.",
            ),
            self.WITHDRAWN: (
                "Enrollment Withdrawn",
                f"You have been withdrawn from {course}.",
            ),
        }
        title, message = texts[self.status]
        Notification.objects.create(
            user=self.user, kind=Notification.ENROLLMENT, title=title, message=message
        )


class Announcement(models.Model):
    title = models.CharField(max_length=150)
    body = models.TextField()
    event_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Notification(models.Model):
    ENROLLMENT, SCHEDULE, REMINDER, ANNOUNCEMENT = "enrollment", "schedule", "reminder", "announcement"
    KIND_CHOICES = [
        (ENROLLMENT, "Enrollment"),
        (SCHEDULE, "Schedule"),
        (REMINDER, "Reminder"),
        (ANNOUNCEMENT, "Announcement"),
    ]
    ICONS = {
        ENROLLMENT: "bi-megaphone-fill",
        SCHEDULE: "bi-calendar3",
        REMINDER: "bi-info-circle-fill",
        ANNOUNCEMENT: "bi-megaphone-fill",
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=15, choices=KIND_CHOICES, default=ENROLLMENT)
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} → {self.user}"

    @property
    def icon(self):
        return self.ICONS.get(self.kind, "bi-bell-fill")


class SiteSetting(models.Model):
    """Singleton row (pk=1) editable from the admin Settings page."""

    system_name = models.CharField(max_length=150, default="TESDA Lucena Management System")
    contact_email = models.EmailField(default="tesda.lucena@tesda.gov.ph")
    default_center = models.ForeignKey(
        TrainingCenter, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        return self.system_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
