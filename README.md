# CleanPool: Bulk Cleaning Service Marketplace

Phase 1 – Account Feature (Django + PostgreSQL/Supabase).
Registration, login/logout with lockout (BR-03), suspension check (BR-04), role-based dashboards (Client / Provider / Admin), and own-profile view/edit.

## Setup
```bash
python -m venv venv
venv\Scripts\activate          # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
cp .env.example .env           # then fill in your PostgreSQL / Supabase credentials
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser   # creates the Admin role account
python manage.py runserver
```
Run tests: `python manage.py test`

## Roles
- **Client / Provider** – self-register at `/register/`
- **Admin** – created with `createsuperuser` (cannot self-register)

Visiting another role's dashboard URL returns 403; logged-out users are redirected to `/login/`.
