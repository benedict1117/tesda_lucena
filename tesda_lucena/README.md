# TESDA Lucena – Batch Availability System (Django)

## Run it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations core                    # first time only (custom User model)
python manage.py migrate
python manage.py seed_demo                              # optional demo data + demo accounts
python manage.py runserver
```

Open http://127.0.0.1:8000/

Demo accounts (from `seed_demo`):

| Role    | Login              | Password     |
|---------|--------------------|--------------|
| Admin   | admin@tesda.local  | admin12345   |
| Trainee | juan@example.com   | juan12345    |

Change these before any real use. To make your own admin: `python manage.py createsuperuser`
(superusers automatically get the Admin role), or set a user's Role to Admin in **Users → Edit**.

Run the tests with `python manage.py test`.

## Access rules

| Who | What happens |
|-----|--------------|
| Guest | Navigation bar (Home, Courses, Training Centers, About, search, Log in, Sign up) works. Every other button (View batches, Check availability, Enroll...) opens a login-protected page, so the guest is sent to **Log in**, with a Register button. After logging in they return to the page they wanted. |
| Trainee | Lands on the user dashboard. Clicking **Training Centers** redirects to **Courses**. Cannot open `/manage/...` (sent back to their dashboard). |
| Admin | Lands on `/manage/` (sidebar dashboard). Public/trainee pages redirect to the admin dashboard. |

The rules live in `core/decorators.py` (`user_required`, `admin_required`, `public_page`) and
`training_centers` in `core/views.py`.

## Pop-ups and notifications

`static/js/app.js` provides the six pop-ups from your design: Notification, Success, Confirmation,
Course info, Exit (logout) and Information. Django messages automatically show as Success/Information pop-ups.
Notifications are created automatically when an enrollment is received/confirmed/withdrawn, when a batch
schedule changes, and when an admin posts an announcement (Admin → Notifications).

## Replace the placeholders

- `static/img/tesda-logo.svg` – placeholder mark; drop in the official TESDA logo with the same name
  (or update the `<img>` paths).
- `static/img/login-hero.jpg` – photo for the login page (optional; a soft gradient shows until added).
