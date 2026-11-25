from django.test import TestCase
from django.urls import reverse

from .models import Batch, Course, Enrollment, TrainingCenter, User


class AccessRulesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("u@example.com", email="u@example.com", password="pw-12345-x", first_name="Una")
        cls.admin = User.objects.create_user(
            "a@example.com", email="a@example.com", password="pw-12345-x", role="admin"
        )
        course = Course.objects.create(name="Cookery", nc_level="NC II", category="TVET")
        center = TrainingCenter.objects.create(name="Center A", address="Lucena")
        cls.batch = Batch.objects.create(
            course=course, center=center, batch_no="B1", start_date="2026-12-01", end_date="2027-01-01", slots=2
        )

    # --- guests
    def test_guest_buttons_go_to_login(self):
        for name, args in [("course_detail", [1]), ("batches", []), ("dashboard", []), ("my_enrollment", [])]:
            r = self.client.get(reverse(name, args=args))
            self.assertRedirects(r, f"{reverse('login')}?next={reverse(name, args=args)}", fetch_redirect_response=False)

    def test_guest_can_see_navigation_pages(self):
        for name in ["home", "courses", "training_centers", "about", "login", "register"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_guest_cannot_open_admin(self):
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 302)

    # --- logged-in trainee
    def test_training_centers_redirects_to_courses_when_logged_in(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("training_centers")), reverse("courses"))

    def test_user_cannot_open_admin_pages(self):
        self.client.force_login(self.user)
        for name in ["admin_dashboard", "manage_courses", "manage_reports", "manage_settings"]:
            self.assertRedirects(self.client.get(reverse(name)), reverse("dashboard"), msg_prefix=name)

    # --- admin
    def test_admin_goes_to_admin_dashboard(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("admin_dashboard"))
        self.assertRedirects(self.client.get(reverse("home")), reverse("admin_dashboard"))

    def test_login_redirects_by_role(self):
        r = self.client.post(reverse("login"), {"username": "a@example.com", "password": "pw-12345-x"})
        self.assertRedirects(r, reverse("admin_dashboard"))
        self.client.logout()
        r = self.client.post(reverse("login"), {"username": "u@example.com", "password": "pw-12345-x"})
        self.assertRedirects(r, reverse("dashboard"))

    def test_login_with_mobile_number(self):
        User.objects.create_user("09171234567", phone="09171234567", password="pw-12345-x")
        r = self.client.post(reverse("login"), {"username": "0917 123 4567", "password": "pw-12345-x"})
        self.assertRedirects(r, reverse("dashboard"))

    # --- enrollment flow + notifications
    def test_enroll_withdraw_and_notifications(self):
        self.client.force_login(self.user)
        self.client.post(reverse("enroll", args=[self.batch.pk]))
        e = Enrollment.objects.get(user=self.user)
        self.assertEqual(e.status, "pending")
        self.assertEqual(self.batch.slots_left, 1)
        e.status = "enrolled"
        e.save()
        titles = list(self.user.notifications.values_list("title", flat=True))
        self.assertIn("Enrollment Confirmed", titles)
        self.client.post(reverse("withdraw"))
        e.refresh_from_db()
        self.assertEqual(e.status, "withdrawn")
        self.assertEqual(self.batch.slots_left, 2)

    def test_second_active_enrollment_blocked(self):
        self.client.force_login(self.user)
        self.client.post(reverse("enroll", args=[self.batch.pk]))
        other = Batch.objects.create(
            course=self.batch.course, center=self.batch.center, batch_no="B2",
            start_date="2027-02-01", end_date="2027-03-01", slots=5,
        )
        self.client.post(reverse("enroll", args=[other.pk]))
        self.assertEqual(Enrollment.objects.filter(user=self.user).count(), 1)

    def test_schedule_change_notifies_enrolled_users(self):
        Enrollment.objects.create(user=self.user, batch=self.batch)
        self.batch.start_date = "2026-12-05"
        self.batch.save()
        self.assertTrue(self.user.notifications.filter(title="Schedule Update").exists())

    def test_admin_csv_reports(self):
        self.client.force_login(self.admin)
        for slug in ["enrollment", "course-availability", "batch", "training-center", "monthly"]:
            r = self.client.get(reverse("manage_report", args=[slug]))
            self.assertEqual(r.status_code, 200, slug)
            self.assertIn("text/csv", r["Content-Type"])
