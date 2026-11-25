from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Announcement, Batch, Course, Enrollment, SiteSetting, TrainingCenter

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo data: 1 admin, 1 trainee, courses, centers, batches, an enrollment and an announcement."

    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            username="admin@tesda.local",
            defaults={"email": "admin@tesda.local", "first_name": "Admin", "is_staff": True,
                      "is_superuser": True, "role": "admin"},
        )
        if created:
            admin.set_password("admin12345")
            admin.save()

        juan, created = User.objects.get_or_create(
            username="juan@example.com",
            defaults={"email": "juan@example.com", "first_name": "Juan", "last_name": "Dela Cruz"},
        )
        if created:
            juan.set_password("juan12345")
            juan.save()

        centers = {}
        for name, addr, contact, programs, lat, lng in [
            ("TESDA Lucena Training Center", "Rizal St., Lucena City", "(042) 373-1234", "Various TVET Programs", 13.9372, 121.6170),
            ("Lucena North Training Center", "Brgy. Ilayang Dupay, Lucena City", "(042) 710-5678", "Technical & Vocational", 13.9610, 121.6200),
            ("Lucena South Training Center", "Brgy. Dalahican, Lucena City", "(042) 710-9876", "ICT and Service Courses", 13.9100, 121.6150),
            ("TESDA Lucena Grand Central Terminal", "Grand Central Terminal, Lucena City", "(042) 373-0000", "Welding and Technical Courses", 13.9320, 121.6240),
        ]:
            centers[name], _ = TrainingCenter.objects.get_or_create(
                name=name,
                defaults={"address": addr, "contact": contact, "programs_offered": programs,
                          "latitude": lat, "longitude": lng},
            )
        c1, c2, c3, c4 = list(centers.values())

        courses = {}
        for name, nc, cat, hours in [
            ("Cookery", "NC II", "TVET", 316),
            ("Electrical Installation and Maintenance", "NC II", "Technical", 360),
            ("Computer Systems Servicing", "NC II", "ICT", 280),
            ("Bread and Pastry Production", "NC II", "Food and Beverage", 296),
            ("Caregiving", "NC II", "Health Care", 786),
            ("Shielded Metal Arc Welding", "NC I", "Technical", 480),
        ]:
            courses[name], _ = Course.objects.get_or_create(
                name=name, nc_level=nc, defaults={"category": cat, "duration_hours": hours}
            )

        specs = [
            ("Cookery", c1, "2026-1A", date(2026, 9, 15), date(2026, 12, 15), 25, "available"),
            ("Electrical Installation and Maintenance", c1, "2026-1B", date(2026, 10, 1), date(2026, 12, 31), 20, "ongoing"),
            ("Computer Systems Servicing", c1, "2026-2A", date(2026, 11, 10), date(2027, 2, 10), 30, "upcoming"),
            ("Bread and Pastry Production", c4, "2026-1C", date(2026, 9, 20), date(2026, 12, 20), 15, "available"),
            ("Shielded Metal Arc Welding", c4, "SMW-1125-01", date(2026, 11, 10), date(2026, 12, 12), 20, "available"),
            ("Caregiving", c2, "2026-3A", date(2027, 1, 12), date(2027, 5, 30), 25, "upcoming"),
        ]
        batches = {}
        for course_name, center, no, start, end, slots, status in specs:
            batches[no], _ = Batch.objects.get_or_create(
                batch_no=no,
                defaults={"course": courses[course_name], "center": center, "start_date": start,
                          "end_date": end, "slots": slots, "status": status},
            )

        if not Enrollment.objects.filter(user=juan).exists():
            enr = Enrollment.objects.create(user=juan, batch=batches["SMW-1125-01"])
            enr.status = "enrolled"
            enr.save()

        Announcement.objects.get_or_create(
            title="Free Career Guidance Seminar",
            defaults={"body": "Join our Career Guidance Seminar on November 5, 2026, 9:00 AM at the TESDA Lucena Training Center.",
                      "event_date": date(2026, 11, 5)},
        )
        SiteSetting.load()
        self.stdout.write(self.style.SUCCESS(
            "Demo data ready.\n  Admin:   admin@tesda.local / admin12345\n  Trainee: juan@example.com / juan12345"
        ))
