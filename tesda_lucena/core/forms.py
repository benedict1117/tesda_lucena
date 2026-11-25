from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Announcement, Batch, Course, Enrollment, SiteSetting, TrainingCenter
from .utils import PHONE_RE, normalize_phone

User = get_user_model()


class StyledMixin:
    """Adds the CSS classes used by static/css/app.css to every widget."""

    def _style(self):
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "check")
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", "input select")
            else:
                w.attrs.setdefault("class", "input")


# ----------------------------------------------------------------- auth forms


class LoginForm(StyledMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"placeholder": "Email or mobile number", "autocomplete": "username", "autofocus": True}
        )
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": "Incorrect email/mobile number or password.",
        "inactive": "This account is inactive.",
    }


class RegisterForm(StyledMixin, forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    first_name =forms.CharField(max_length=60, widget=forms.TextInput(attrs={"placeholder": "First name"}))
    last_name = forms.CharField(max_length=60, widget=forms.TextInput(attrs={"placeholder": "Last name"}))
    identifier = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Email or mobile number", "autocomplete": "username"}),
    )
    password1 = forms.CharField(
        strip=False, widget=forms.PasswordInput(attrs={"placeholder": "Password", "autocomplete": "new-password"})
    )
    password2 = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password", "autocomplete": "new-password"}),
    )

    def clean_identifier(self):
        ident = self.cleaned_data["identifier"].strip()
        if "@" in ident:
            try:
                validate_email(ident)
            except ValidationError:
                raise ValidationError("Enter a valid email address.")
            if User.objects.filter(email__iexact=ident).exists():
                raise ValidationError("An account with this email already exists.")
            self.kind, self.value = "email", ident.lower()
        else:
            phone = normalize_phone(ident)
            if not PHONE_RE.match(phone):
                raise ValidationError("Enter a valid email address or mobile number.")
            if User.objects.filter(phone=phone).exists():
                raise ValidationError("An account with this mobile number already exists.")
            self.kind, self.value = "phone", phone
        return ident

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        elif p1:
            try:
                validate_password(p1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data

    def save(self):
        d = self.cleaned_data
        return User.objects.create_user(
            username=self.value,
            email=self.value if self.kind == "email" else None,
            phone=self.value if self.kind == "phone" else None,
            password=d["password1"],
            first_name=d["first_name"].strip(),
            last_name=d["last_name"].strip(),
            role=User.ROLE_USER,
        )


# --------------------------------------------------------------- admin forms


class CourseForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Course
        fields = ["name", "nc_level", "category", "duration_hours", "provider", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class TrainingCenterForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = TrainingCenter
        fields = ["name", "address", "contact", "programs_offered", "status", "latitude", "longitude"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class BatchForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["course", "center", "batch_no", "start_date", "end_date", "schedule_time", "slots", "status"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["course"].queryset = Course.objects.filter(is_active=True)
        self.fields["center"].queryset = TrainingCenter.objects.filter(status="active")
        self._style()

    def clean(self):
        data = super().clean()
        s, e = data.get("start_date"), data.get("end_date")
        if s and e and e < s:
            self.add_error("end_date", "End date cannot be before the start date.")
        return data


class EnrollmentForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ["user", "batch", "status", "enrolled_on"]
        widgets = {"enrolled_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["user"].queryset = User.objects.filter(role=User.ROLE_USER)
        self.fields["user"].label_from_instance = lambda u: f"{u.full_display_name} ({u.email or u.phone})"
        self._style()


class UserEditForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role", "is_active"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class AnnouncementForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "body", "event_date"]
        widgets = {
            "body": forms.Textarea(attrs={"rows": 4}),
            "event_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class GeneralSettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ["system_name", "contact_email", "default_center"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()


class NotificationSettingsForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ["email_notifications"]
        labels = {"email_notifications": "Send email copies of announcements"}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._style()
