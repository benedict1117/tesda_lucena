from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def role_required(role):
    """Guests -> login page. Wrong role -> that role's own home page."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role != role:
                return redirect("admin_dashboard" if request.user.is_admin_role else "dashboard")
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


user_required = role_required("user")
admin_required = role_required("admin")


def public_page(view):
    """Public pages are for guests and trainees; admins are sent to their own area."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_admin_role:
            return redirect("admin_dashboard")
        return view(request, *args, **kwargs)

    return wrapper
