from django.contrib import messages

from .models import SiteSetting


def site(request):
    ctx = {"site": SiteSetting.load()}
    # Django messages -> JSON so static/js/app.js can show them as pop-ups.
    ctx["flash_messages"] = [
        {"level": m.level_tag, "text": str(m.message)} for m in messages.get_messages(request)
    ]
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and not user.is_admin_role:
        ctx["unread_count"] = user.notifications.filter(is_read=False).count()
    return ctx
