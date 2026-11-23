# CleanPool: Bulk Cleaning Service Marketplace

**Phase 1 – Account Feature** (Django + PostgreSQL/Supabase).
Registration, login/logout with lockout (BR-03), suspension check (BR-04), role-based dashboards (Client / Provider / Admin), and own-profile view/edit.

## Setup
```bash
python -m venv venv
venv\Scripts\activate          # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
cp .env.example .env           # then fill in your PostgreSQL / Supabase credentials
python manage.py migrate
python manage.py createsuperuser   # creates the Admin role account
python manage.py seed_demo         # optional: demo accounts + sample service/pool
python manage.py runserver
```
Run tests: `python manage.py test`

## Roles
- **Client / Provider** – self-register at `/register/`
- **Admin** – created with `createsuperuser` (cannot self-register)

Visiting another role's dashboard URL returns 403; logged-out users are redirected to `/login/`.

## Phase 2 – Core Feature: Pooled Cleaning Bookings

CleanPool lets small businesses **pool** their cleaning needs so they can share one provider's booking and unlock a volume discount.

**Flow**
1. **Provider** creates a *Service* (title, area, price per sqm) and adds *discount tiers* (e.g. 3+ businesses → 10% off), then publishes it.
2. **Client** starts a *Pool* on a published service (location, date, max businesses) and enters their own business and area. Other clients browse open pools and **join** with their own area. The per-sqm rate drops automatically as more businesses join.
3. **Provider** reviews pools on their services and **confirms** (needs at least 2 businesses), **declines**, or marks **completed**. A confirmed pool is locked for members.
4. **Admin** oversees all pools and can cancel any open/confirmed pool.

**CRUD:** Service, PricingTier, Pool and PoolMembership can each be created, read, updated and deleted through the UI by the right role.

**Business rules**
- Only logged-in users; each role sees its own pages (others get 403). Records are tied to their creator by ForeignKey and users can only change their own.
- Pool date must be in the future, 2–50 businesses, area at least 10 sqm, one membership per business per pool, no joining a full/non-open pool.
- Pool can be edited/cancelled by its creator only while open; it can be deleted only if no other business joined.
- A service with pools cannot be deleted (`PROTECT`).

**Models:** `Service` → `PricingTier` (1-N), `Service` → `Pool` (1-N), `Pool` → `PoolMembership` (1-N), `User` → `Service`/`Pool`/`PoolMembership` (1-N).

**Demo accounts** (`python manage.py seed_demo`, password `CleanPool#2026`): `client1@cleanpool.test`, `client2@cleanpool.test`, `provider@cleanpool.test`, `admin@cleanpool.test`.

## Git workflow
`main` (stable) ← `develop` (integration) ← `feature/<name>` (one per feature, via Pull Request).
Branches for this phase: `feature/service-management`, `feature/pool-booking`.
