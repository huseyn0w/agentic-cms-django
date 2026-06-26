# Cmstack-Django

An open-source CMS built on Python/Django — lighter, faster, SEO-first, and easy to
read, understand, and extend. It ships its own admin panel, a swappable theme + plugin
system, multilingual content, a first-class SEO/GEO layer, a public REST API, and an MCP
server so you can manage the site from an AI assistant.

> **Status:** feature-complete core. Content, media, the custom admin, themes, plugins,
> multilingual (en/de), SEO/GEO (JSON-LD, sitemap, robots, `llms.txt`, Service pages),
> comments, search, menus, soft-delete/trash, revision restore, scheduled publishing,
> author pages, in-editor media picker, REST API + MCP — all built and tested. CI runs
> ruff + black + mypy + pytest (with a PostgreSQL full-text-search job) + a Playwright
> e2e job. Lighthouse ≥ 95 across performance / accessibility / best-practices / SEO.

This is the Django implementation in a family of parallel CMS stacks that share two
read-only specs: [`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md) (capability parity across
stacks) and [`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md) (the shared visual language).

## Stack

- Python 3.12, Django 5.1
- PostgreSQL (default; ORM kept DB-agnostic so MySQL works on shared hosting)
- Tailwind CSS 3 + Alpine.js, bundled with Vite via `django-vite`
- Rich-text editor: Trix (admin), all HTML sanitized server-side with **nh3** on every save
- Auth + social login: **django-allauth** (username/email login + Google)
- Multilingual content: **django-parler** (per-language translation tables, hreflang)
- Public read/write API: **Django REST Framework**; AI management surface: a small **MCP** server
- Tests: **pytest** + pytest-django + Playwright (e2e) · Lint/format: **ruff** + **black** ·
  Types: **mypy** (django-stubs)
- Local infra: Docker + docker compose · Prod: gunicorn + nginx + whitenoise

## Requirements

- Docker + docker compose (the quick path), **or** Python 3.12 + Node 20 + a PostgreSQL you
  point `DATABASE_URL` at.

## Quick start (Docker)

```bash
cp .env.example .env          # defaults work out of the box
docker compose up --build
```

Open <http://localhost:8000> — the styled landing page renders the CMS's own recent posts.
The web container waits for Postgres, runs migrations, and serves the app on port 8000.

```bash
docker compose exec web python manage.py createsuperuser   # an admin to sign in with
```

## Local development (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

cd frontend && npm install && npm run build && cd ..   # Tailwind + Alpine via Vite

# point DATABASE_URL at a local Postgres, or export POSTGRES_* (see .env.example)
python manage.py migrate
python manage.py runserver
```

For live frontend reloads, run the Vite dev server and set `DJANGO_VITE_DEV_MODE=True`:

```bash
cd frontend && npm run dev      # HMR on :5173
```

## Architecture

Cmstack-Django is idiomatic Django organized as focused apps (one app = one bounded
concern). Beyond that it enforces a strict, one-directional layering so views stay thin
and business logic stays testable:

```
view → service → repository → manager / QuerySet → model
                    └── side effects: service → Django signal → receiver
```

Two non-negotiable rules hold in every app:

1. **Views are the HTTP boundary only.** `apps/*/views.py` contain zero business logic and
   zero ORM access — they parse the request, call a service, and map the result to a
   response (status, redirect, template).
2. **Services never touch the ORM.** `apps/*/services.py` orchestrate use-cases purely
   through `apps/<app>/repositories.py`; data access lives in repositories, which call
   model managers / querysets. Side effects (emails, notifications) are emitted as Django
   signals and handled by receivers, not inlined into the service.

Entity behaviour (invariants, state transitions like `Post.trash()` /
`Comment.approve()` / `Post.restore_revision()`) lives on the models and is called by
services — that is domain logic, not "ORM in a service".

**Design patterns — used only where they remove real duplication, never speculatively:**

- **Repository** — every app's data access (`*/repositories.py`).
- **Service / use-case** — every app's orchestration (`*/services.py`), returning outcome
  enums where the view needs to branch (e.g. `comments.submit_comment`).
- **Observer** — Django signals decouple side effects (comment-notification + contact
  emails) from the services that trigger them (`apps/comments/signals.py`,
  `apps/core/signals.py`).
- **Strategy** — search picks a backend at query time (PostgreSQL `SearchVector` vs a
  DB-agnostic `icontains` fallback); storage swaps local disk ↔ S3 via Django `STORAGES`.
- **Registry** — themes and plugins are runtime registries resolved per render, so neither
  needs a restart to switch.

## Project layout

```
config/            # Django project: settings split (base/dev/prod/test/test_postgres/test_e2e)
apps/              # one Django app per bounded concern, each with views/services/repositories
  accounts/        # custom User, roles (Groups), permissions, allauth + Google, author pages
  content/         # posts/pages/services, taxonomy, revisions, soft-delete, scheduling, likes
  media/           # media library: uploads, validation, thumbnails, in-editor picker, storage
  dashboard/       # the custom admin panel (own UI, not the Django admin)
  themes/          # theme registry + runtime template loader
  plugins/         # hook registry + plugin enable/disable
  seo/             # SEO/GEO: settings, meta/JSON-LD, sitemap, robots, llms.txt, Service pages
  comments/        # threaded, moderated comments on posts (+ reCAPTCHA when configured)
  search/          # public search over published posts/pages (Postgres FTS or fallback)
  menus/           # managed navigation menus (header/footer)
  api/             # public REST API (read + gated write) + health probes
  mcp/             # MCP server — manage the site from an AI assistant
  core/            # landing page, SiteSettings, contact form, shared bits
themes/            # the themes themselves (default, midnight) — each a template set
plugins/           # the plugins themselves (e.g. reading_time) — each a Django app
frontend/          # Vite + Tailwind + Alpine source (builds to frontend/dist)
templates/         # project-level base templates + shared shell partials
tests/e2e/         # Playwright browser journeys (auth, content, SEO, i18n, theme)
requirements/      # base / dev / prod dependency sets
.github/workflows/ # CI pipeline
```

## Features

**Accounts, roles & permissions.** django-allauth login (username or email, or Google).
Roles are Django **Groups** synced idempotently from `apps/accounts/roles.py` on every
`post_migrate`: Administrator, Editor, Author, Contributor, Subscriber. Everything uses
standard Django permissions, so `has_perm`, `@permission_required`, and
`PermissionRequiredMixin` all work. Public **author pages** (`/authors/<id>/`, gated to
published authors, email never rendered, `ProfilePage`/`Person` JSON-LD) and a
self-service profile editor at `/account/`.

**Content.** Posts, pages, hierarchical categories, tags, and per-type revisions. Bodies
are sanitized with nh3 on every save, so stored HTML is always safe (`|safe` at render is
deliberate). Soft-delete with trash/restore + permanent-delete; per-language revision
history with a difflib diff and one-click restore; scheduled (future) publishing via a
`publish_scheduled` cron command; post likes. Public at `/blog/…`, `/pages/<slug>/`,
`/services/<slug>/`; drafts 404 for anonymous visitors but preview for editors.

**Media.** `MediaAsset` stores files + extracted metadata + a Pillow thumbnail; uploads
are validated (SVG rejected as an XSS vector). An in-editor picker drops library images
into Trix. Storage is swappable — local disk by default, S3-compatible (MinIO/R2) when
`USE_S3_MEDIA=1` — with no model change.

**Admin panel.** A bespoke dashboard at `/dashboard/` (not the Django admin), gated by
`accounts.access_admin`. Dark-mode toggle (no FOUC), accessible confirm dialogs, toast
notifications, table bulk actions, breadcrumbs, accessible pagination, and per-language
editing tabs. Authors/Contributors are scoped to their own posts.

**Themes & plugins.** Themes live in `themes/<slug>/` and are resolved at runtime by a
template loader (no restart to switch); a theme recolors the site by overriding CSS-variable
tokens only — it never forks the shell. Plugins are Django apps registered through a small
hook registry (`do_action` / `apply_filters` / `render_hook`), toggled at runtime.

**SEO / GEO.** A first-class SEO/GEO app: per-content meta + Open Graph/Twitter, JSON-LD
(`Organization`, `WebSite`, `Article`, `BreadcrumbList`, `Person`, `Service`, `FAQPage`),
`sitemap.xml` with hreflang alternates, dynamic `robots.txt` with per-bot answer-engine
policy, and `llms.txt` / `llms-full.txt`. A GEO-optimized **Service** page type pairs a
definitional summary + Q&A with `Service` + `FAQPage` schema — the format answer engines
quote.

**Comments, search & menus.** Threaded, moderated comments (pending by default; optional
login-required; invisible reCAPTCHA when keys are set). Public search over published
posts/pages — PostgreSQL full-text search where available, a DB-agnostic fallback
elsewhere. Managed header/footer navigation menus with a keyboard-accessible builder.

**REST API & MCP.** A DRF read API at `/api/v1/` (published-only, parler-aware, `?lang=`),
gated post writes (token + model-permission, owner-scoped, publish gated server-side),
and `/health/` + `/health/ready/` probes. An **MCP** server at `POST /api/mcp/` exposes a
13-tool registry (posts CRUD + publish, list endpoints, comment moderation, settings) that
re-verifies each tool's permission server-side — so you can drive the CMS from Claude.
Mint tokens with `python manage.py create_api_token <user>`.

## Commands

| Task               | Command                                                              |
| ------------------ | ------------------------------------------------------------------- |
| Dev up             | `docker compose up`                                                  |
| Migrate            | `docker compose exec web python manage.py migrate`                  |
| Create admin user  | `docker compose exec web python manage.py createsuperuser`         |
| Publish scheduled  | `python manage.py publish_scheduled` (run from cron, e.g. minutely) |
| Mint an API token  | `python manage.py create_api_token <user>`                          |
| Tests              | `pytest` (or `docker compose exec web pytest`)                       |
| Single test        | `pytest apps/core/tests/test_home.py::test_home_status_ok`          |
| Lint / format / types | `ruff check .` · `black .` · `mypy apps config`                  |
| Frontend build     | `cd frontend && npm run build` (watch: `npm run dev`)               |

## Testing

```bash
pytest                                    # full unit/integration suite (SQLite, fast)
pytest --cov=apps --cov-report=term-missing   # with coverage (~96%)
```

End-to-end browser journeys (Playwright) are excluded from the default run. They drive a
real headless Chromium against a live server serving the built bundle:

```bash
playwright install chromium
cd frontend && npm run build && cd ..
pytest tests/e2e -m e2e --ds=config.settings.test_e2e
```

The PostgreSQL full-text-search branch is only exercised on Postgres; CI runs the suite a
second time with `--ds=config.settings.test_postgres` against a Postgres service to cover
it. Lighthouse is measured against a built, Postgres-backed server (home and post detail
both score ≥ 95 on performance / accessibility / best-practices / SEO).

## Internationalization

`LANGUAGES = en, de`. Translated fields live in per-language parler tables; the slug,
status, author and taxonomy FKs stay shared, so one record has one stable slug and the URL
language prefix differentiates languages. Public + core URLs are wrapped in
`i18n_patterns(prefix_default_language=False)`: the default language keeps clean URLs
(`/blog/<slug>/`), others are prefixed (`/de/blog/<slug>/`). hreflang alternates and a
header language switcher are emitted only where the per-language URLs differ. The dashboard
edits one language at a time via `?language=xx` tabs.

## Continuous integration

`.github/workflows/ci.yml` runs on every push/PR:

- **lint** — `ruff check` + `black --check` + `mypy apps config`
- **test** — `pytest` + coverage on SQLite (90% floor)
- **test-postgres** — the suite on PostgreSQL to exercise the full-text-search branch
- **frontend** — the Vite production build
- **e2e** — Playwright journeys against a live server with the built bundle

## Deployment

Production runs gunicorn behind nginx with whitenoise serving the collected static +
built frontend assets. Settings are chosen by `DJANGO_SETTINGS_MODULE`
(`config.settings.prod` is hardened); all configuration is environment-driven (`.env`,
documented in `.env.example`) — never commit secrets. Media can stay on local disk or move
to an S3-compatible bucket (`USE_S3_MEDIA=1`). The ORM is kept DB-agnostic so MySQL works
for shared hosting.

## Roadmap & parity

Capability parity with the reference CMS and the sibling stacks is tracked in
[`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md); the shared visual language is
[`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md). The reference implementation (Laravel) is
[Laravella-CMS](https://github.com/huseyn0w/Laravella-CMS).

## License

See [LICENSE](LICENSE).
