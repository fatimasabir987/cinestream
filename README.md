# CineStream: Flask Streaming Platform

A Flask, SQLAlchemy and Jinja2 web app for browsing movies, reviewing them, building
watchlists and managing a subscription. Built against the Web Engineering (CSE601330)
Flask rubric for Weeks 5-8.

## Rubric coverage

| Criterion | How it is met |
|---|---|
| Project setup (10) | Virtual env, pinned `requirements.txt`, application factory, `templates/` and `static/` folders |
| Routing and views (15) | Blueprints for auth, catalog, account and admin; `<int:id>` converters; GET for reads, POST for every write |
| Templates (15) | `base.html` inheritance across all pages; shared macros in `_macros.html`; loops and conditionals |
| Database and CRUD (20) | 42 SQLAlchemy models with foreign keys, unique and check constraints; CRUD for every table (admin) and CRUD for reviews, watchlists, favourites and comments (users) |
| Forms, validation, sessions (15) | Server-side WTForms validation (unique username and email, password rules, score range); CSRF on all forms; session login with fixation protection; flash messages; POST-Redirect-GET; "recently viewed" cookie |
| Code quality (10) | Single-responsibility modules, one generic CRUD engine instead of 42 hand-written copies |
| Functionality and testing (10) | `pytest` suite (11 tests) covering schema, pages, validation, access control, admin CRUD and billing |
| Documentation (5) | This README |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app run seed                 # load demo data (safe to run more than once)
flask --app run run --debug          # open http://127.0.0.1:5000
```

Demo accounts (development only, change them before any real deployment):

| Username | Password    | Role   |
|----------|-------------|--------|
| admin    | Admin12345  | admin  |
| viewer   | Viewer12345 | member |
| critic   | Critic12345 | member |

Admin console: log in as `admin`, then open `/admin/`.

## Environment variables

| Name           | Default                   | Purpose                        |
|----------------|---------------------------|--------------------------------|
| `SECRET_KEY`   | `dev-only-change-me`      | Signs sessions and CSRF tokens |
| `DATABASE_URL` | `sqlite:///cinestream.db` | Any SQLAlchemy database URL    |

## Running tests

```bash
pytest
```

## Database schema (42 tables)

- **Accounts and billing (14):** roles, users, profiles, countries, addresses, payment_methods, plans, subscriptions, invoices, invoice_lines, payments, coupons, coupon_redemptions, devices
- **Catalog (18):** studios, languages, genres, content_ratings, franchises, movies, movie_genres, people, professions, person_professions, credit_types, movie_credits, awards, movie_awards, keywords, movie_keywords, trailers, subtitles
- **Engagement (10):** watchlists, watchlist_items, reviews, review_votes, review_comments, watch_history, favorites, notifications, user_settings, follows

Join tables (`movie_genres`, `movie_credits`, `watchlist_items`, `movie_keywords`, `person_professions`, and others) model many-to-many relationships. Every table takes part in at least one relationship.

## Project layout

```
run.py              entry point and the `seed` CLI command
config.py           configuration classes
app/
  __init__.py       application factory, extensions, blueprint registration
  models.py         all 42 models
  crud.py           builds admin forms and save logic from model columns
  forms.py          hand-written forms with server-side validation
  utils.py          login_required, admin_required, safe redirects
  auth.py           register, login, logout
  catalog.py        browsing, movie pages, reviews, comments, votes
  account.py        dashboard, watchlists, favourites, progress, plans, billing
  admin.py          admin console (list, create, edit, delete for every table)
  seed.py           demo data
templates/          Jinja2 templates
static/css/         stylesheet
tests/              pytest suite
```

## Notes

- Titles, people, reviews and studios are fictional. Posters are placeholder images.
- Payments are simulated; no card is charged.
- To use real movie metadata later, a TMDB import script could fill the same tables. Check TMDB's terms before storing or displaying its images.

## Audit, soft delete and status (every table)

Every one of the 42 tables inherits `AuditMixin` (`app/models.py`):

| Column | Meaning |
|---|---|
| `created_at` / `created_by_id` | When and by whom the row was created (set automatically) |
| `updated_at` / `updated_by_id` | When and by whom the row was last changed (set automatically) |
| `is_deleted` / `deleted_at` / `deleted_by_id` | Soft delete: the row is hidden, never removed from the database |
| `status` | `active` by default; editable in the admin forms |

- Deleting in the admin console or on the site sets `is_deleted`. Restore a row at `/admin/<table>/` with **Restore**.
- Every query skips soft-deleted rows automatically, so public pages return 404 for them.
- Tables that already had a domain status (`subscriptions`, `invoices`, `payments`) keep it. Their `status` column is the domain value (for example `paid`, `cancelled`).
- Re-adding a removed favourite, watchlist item, review or vote restores the old row instead of inserting a duplicate, because the unique constraints still apply.

**Upgrading an older copy:** the schema changed, so delete `cinestream.db` and run `flask --app run seed` again.
