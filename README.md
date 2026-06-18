# DjangoPress

An open-source, WordPress-style CMS built on Python/Django — lighter, faster, SEO-first,
and easy to read, understand, and extend.

> **Status:** Phases 1–7 complete (Foundation, Accounts, Content, Media, Admin, Themes, Plugins).
> Phase 8 (SEO/GEO) in progress — slices 8.1 (multilingual + hreflang), 8.2 (SEO core: meta/OG/Twitter,
> canonical, robots, per-content SEO fields, SEO settings) and 8.3 (JSON-LD structured data) shipped.
> See the roadmap below.

## Stack

- Python 3.12, Django 5.1
- PostgreSQL (default; ORM kept DB-agnostic so MySQL works on shared hosting)
- Tailwind CSS 3 + Alpine.js, bundled with Vite via `django-vite`
- Rich-text editor: Trix (admin), with all HTML sanitized server-side
- Auth + social login: django-allauth (username/email login + Google)
- Multilingual content: django-parler (per-language translation tables, hreflang)
- Rich-text sanitization: nh3 (server-side, on every save)
- Tests: pytest + pytest-django · Lint/format: ruff + black · Types: mypy
- Local infra: Docker + docker compose · Prod: gunicorn + nginx + whitenoise

## Quick start (Docker)

```bash
cp .env.example .env          # adjust if you like; defaults work out of the box
docker compose up --build
```

Then open <http://localhost:8000> — you should see the styled DjangoPress landing page.
The web container waits for Postgres, runs migrations, and serves the app on port 8000.

## Local development (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

# Frontend assets (Tailwind + Alpine via Vite)
cd frontend && npm install && npm run build && cd ..

# Run against a local Postgres, or export DATABASE_URL
python manage.py migrate
python manage.py runserver
```

For live frontend reloads, run the Vite dev server and enable dev mode:

```bash
cd frontend && npm run dev           # serves on :5173 with HMR
# in .env: DJANGO_VITE_DEV_MODE=True
```

## Project layout

```
config/            # Django project: settings split (base/dev/prod/test), urls, wsgi/asgi
  settings/
apps/              # Django apps, one per bounded concern
  accounts/        # custom User, roles (Groups), permissions, allauth + Google
  content/         # posts, pages, categories, tags, revisions, sanitization
  media/           # media library: uploads, validation, thumbnails
  dashboard/       # custom WordPress-style admin panel (own UI)
  themes/          # theme registry + runtime template loader
  plugins/         # hook registry + plugin enable/disable
  core/            # landing page, SiteSettings, shared bits
themes/            # the themes themselves (default, midnight), each a template set
plugins/           # the plugins themselves (e.g. reading_time), each a Django app
frontend/          # Vite + Tailwind + Alpine source (builds to frontend/dist)
templates/         # project-level base templates
docker/            # entrypoint and container helpers
requirements/      # base / dev / prod dependency sets
```

## Common commands

| Task | Command |
| --- | --- |
| Dev up | `docker compose up` |
| Migrate | `docker compose exec web python manage.py migrate` |
| Create admin user | `docker compose exec web python manage.py createsuperuser` |
| Tests | `docker compose exec web pytest` (or `pytest` in a local venv) |
| Single test | `pytest apps/core/tests/test_home.py::test_home_status_ok` |
| Lint / format | `ruff check .` · `black .` |
| Frontend build | `cd frontend && npm run build` (watch: `npm run dev`) |

## Accounts, roles & permissions

Authentication is handled by [django-allauth](https://docs.allauth.org): users sign in
with username **or** email and password, or via Google (set `GOOGLE_CLIENT_ID` /
`GOOGLE_CLIENT_SECRET`). Auth pages live under `/accounts/` (`/accounts/login/`,
`/accounts/signup/`, …) and use a styled DjangoPress layout.

Roles are WordPress-style and implemented as Django **Groups**, kept in sync by a
`post_migrate` hook (`apps/accounts/signals.py`) from a single definition in
`apps/accounts/roles.py`:

| Role | Capabilities (grows as later phases add models) |
| --- | --- |
| Administrator | All content/media/comment permissions + manage users & settings |
| Editor | All content/media + comment moderation; no user/settings management |
| Author | Create / edit / publish own posts, upload media |
| Contributor | Draft posts only (no publish, no media) |
| Subscriber | Authenticated reader; default role for new signups |

Permissions are standard Django permissions, so `user.has_perm(...)`,
`@permission_required`, and `PermissionRequiredMixin` all work. The sync is idempotent
and only assigns permissions whose models exist, so the table fills in across phases.

## Content

The `content` app provides the core CMS data model:

- **Posts** — title, auto unique slug, author, excerpt, sanitized rich-text body,
  featured image, draft/published status, categories (M2M) and tags (M2M). Publishing
  stamps `published_at`; `Post.objects.published()` is the public queryset.
- **Pages** — standalone, optionally hierarchical (e.g. About, Contact).
- **Categories** (hierarchical) and **Tags**.
- **Revisions** — every save of a post/page snapshots a `PostRevision`/`PageRevision`.

**Security:** all rich-text bodies are sanitized server-side with
[nh3](https://nh3.readthedocs.io) on every save (`apps/content/utils.py`), so stored
HTML is always safe regardless of what the editor or request sends. Templates render
the body with `|safe` precisely because it was cleaned at write time.

Public URLs: `/blog/` (list), `/blog/<slug>/` (post), `/blog/category/<slug>/`,
`/blog/tag/<slug>/`, `/pages/<slug>/`. Drafts return 404 to anonymous visitors but are
previewable by users with `content.change_post` / `content.change_page`.

> Content is editable via the interim Django admin (`/admin/`) for now; the bespoke,
> WordPress-style admin panel (dashboard, WYSIWYG editor, media picker, menus, settings)
> is **Phase 5**. The Django admin here is developer scaffolding, not the final admin UX.

## Media library

The `media` app manages uploads (`apps/media/`):

- **`MediaAsset`** — stores the file plus extracted metadata (MIME type, size, image
  width/height) and an auto-generated **thumbnail** (Pillow, max 400×400). Metadata and
  thumbnail are computed on first save.
- **Upload validation** — allowed types are JPG, PNG, GIF, WebP, PDF, capped at 10 MB.
  **SVG is rejected by design** (it can carry embedded scripts → stored-XSS risk).
- **Permission-gated views** — `/library/` (browse grid), `/library/upload/`,
  `/library/<id>/delete/`, each behind `LoginRequiredMixin` + the matching
  `media.*_mediaasset` permission. Editors/Admins get full access; Authors can upload but
  not delete; Contributors have no media access.

Uploaded files live under `MEDIA_ROOT` and are served at `/media/` (by Django in dev, by
the web server / object storage in production). Interim management is also available in the
Django admin; the polished picker integrates with the post editor in Phase 5.

## Admin panel

DjangoPress ships its own WordPress-style admin (the `dashboard` app) — not the bare
Django admin — at **`/dashboard/`**, gated by the `accounts.access_admin` capability:

- **Dashboard** — at-a-glance counts and recent posts.
- **Posts / Pages** — full CRUD with a **Trix** rich-text editor (output sanitized by nh3),
  slug, excerpt, taxonomy, featured image, and draft/publish. Authors and Contributors are
  **scoped to their own content**; Contributors can only save drafts (publishing is gated
  on `content.publish_post`).
- **Categories / Tags** — manage taxonomy.
- **Media** — the media library (Phase 4), linked from the admin nav.
- **Users** — list and assign roles (gated by `accounts.manage_users`).
- **Settings** — site name, tagline, posts-per-page (gated by `accounts.manage_settings`).

Every view is permission-gated, and the sidebar only shows sections the user may access.
The legacy Django admin remains at `/admin/` as a superuser fallback.

> **Frontend rebuilds & Docker:** the dev container surfaces the image's built assets
> through an anonymous volume. After changing anything in `frontend/`, rebuild with
> `docker compose up -d --build --renew-anon-volumes` (or `docker compose down -v` first)
> so the new assets are picked up. A fresh `docker compose up --build` always works.

## Themes

The public site is rendered through a **swappable theme** resolved at runtime. A theme is
a directory under `themes/` with a `theme.json` and an optional `templates/` set that
overrides any project/app template:

```
themes/
  default/   theme.json                      # the base look (no overrides needed)
  midnight/  theme.json  templates/public_base.html   # a dark recolor
```

- A custom template loader (`apps/themes/loaders.py`) is registered ahead of the
  filesystem/app loaders, so the **active theme's** templates win. Resolution is dynamic,
  so switching themes takes effect immediately — no restart.
- The palette is driven by **CSS variables** (`--color-paper/ink/accent`), so a theme can
  recolor the whole public site just by overriding those variables in its `public_base.html`
  — which is exactly what `midnight` does.
- The active theme is stored on `SiteSettings.active_theme` and changed from the admin under
  **Appearance** (gated by `accounts.manage_settings`).

To add a theme: create `themes/<slug>/theme.json`, add template overrides under
`themes/<slug>/templates/`, rebuild the frontend (Tailwind scans `themes/`), and activate it
in **Dashboard → Appearance**.

## Plugins

DjangoPress is extended through a small **hook registry** (`apps/plugins/hooks.py`) —
WordPress-style actions and filters — plus Django's own signals, never arbitrary code
injection. A plugin is a Django app under `plugins/` that registers hooks in its
`AppConfig.ready()`:

- **Filters** transform a value: `apply_filters("post_content", body, post=...)`.
- **Actions** run side effects: `do_action("name", ...)`.
- **Region hooks** inject template HTML: `{% hook "public_footer" %}`.

Hooks are ordered by priority and are **plugin-scoped**: a callback's plugin is inferred
from its module, and callbacks of a disabled plugin are skipped at call time — so plugins
toggle on/off at runtime (no restart) from **Dashboard → Plugins** (gated by
`accounts.manage_settings`). Enable state lives on the `Plugin` model.

The bundled example, **`plugins/reading_time`**, registers a `post_content` filter that
prepends a "☕ N min read" badge to every post. Disable it in the admin and it vanishes.

To write a plugin: create `plugins/<name>/` with an `apps.py` (an `AppConfig` carrying
`plugin_description` / `plugin_version` and a `ready()` that imports its `hooks`), add it to
`INSTALLED_APPS`, and register filters/actions with the `apps.plugins.hooks` helpers.

## Internationalization (multilingual content)

Content is multilingual via [django-parler](https://django-parler.readthedocs.io). Posts,
pages, categories and tags keep their **text** (title, body, excerpt, name, description) in
per-language translation tables, while structural fields (slug, status, publish date, author,
taxonomy) are shared — so each record has **one stable slug** and the URL's language prefix
selects the language.

- **Languages:** configured in `LANGUAGES` (ships with English + German; English is the
  default). `LANGUAGE_CODE = "en"`.
- **URLs:** the default language keeps clean URLs (`/blog/<slug>/`); every other language is
  served under its prefix (`/de/blog/<slug>/`), wired with `i18n_patterns`. The admin,
  dashboard, auth and media URLs are not language-prefixed.
- **hreflang:** every public page advertises `rel="alternate" hreflang="…"` links for each
  language plus `x-default`, and a language switcher in the header — so search and answer
  engines can discover and serve the right language version.
- **Editing:** in the dashboard editor a language tab strip (`?language=xx`) lets you write
  each language's translation independently; missing translations fall back to the default
  language so a half-translated site still renders. Rich-text is nh3-sanitized per language
  on every save.

To add a language, add it to `LANGUAGES` in the settings and translate content from the
dashboard — no migration needed (parler stores languages as rows, not columns).

## SEO (on-site)

The `seo` app renders a complete, server-side `<head>` for every public page and lets you
control it per page and site-wide:

- **Per-content SEO** — each post and page has a meta title and meta description (translated
  per language), a canonical URL, a “hide from search engines” (noindex) toggle, and a social
  share image, edited in a collapsible **SEO & sharing** panel in the editor. Title/description
  fall back to the content's own title/excerpt when left blank.
- **`<head>` output** — `<title>`, meta description, canonical link, robots directive,
  Open Graph and Twitter Card tags, `og:locale`, plus site verification and Google
  Analytics/Tag Manager snippets — all from one `{% seo_head %}` tag. The admin and login
  pages opt out, so analytics and indexing only apply to the public site.
- **Site-wide SEO settings** (Dashboard → SEO) — Open Graph defaults and share image, default
  meta description, Twitter handle, GA/GTM IDs (format-validated), Google/Bing verification
  tokens, and a **Discourage search engines** switch that applies a site-wide `noindex`
  (handy for staging).

- **Structured data (JSON-LD)** — every public page carries `Organization` and `WebSite`
  schema; posts add `Article` (with `Person` author and `Organization` publisher) and a
  `BreadcrumbList`. This is how answer engines (ChatGPT, Perplexity, Google AI Overviews)
  extract who you are and what a page is about. Organization identity (logo + social
  profiles → `sameAs`) is set in Dashboard → SEO. Values are escaped so structured data
  can't be used to inject markup.

`sitemap.xml`, an AI-crawler `robots.txt`, `llms.txt`, and a GEO-optimized Service page
type follow in the remaining Phase 8 slices.

## Configuration

All configuration is via environment variables (see [.env.example](.env.example)); no
secrets are committed. `DJANGO_SETTINGS_MODULE` selects the settings module
(`config.settings.dev` or `config.settings.prod`); the test suite always uses
`config.settings.test` (in-memory SQLite, no external services).

## Roadmap

1. **Foundation** — Docker, Django skeleton, settings split, pytest, ruff/black, Tailwind+Vite ✅
2. **Accounts** — custom user, roles (Groups), granular permissions, allauth + Google login ✅
3. **Content** — posts, pages, categories, tags, revisions, server-side sanitized rich text ✅
4. **Media** — media library, validated uploads, Pillow thumbnails, permission-gated ✅
5. **Admin panel** — custom WordPress-style dashboard (own UI), Trix editor, ownership scoping ✅
6. **Themes** — swappable template sets resolved at runtime, CSS-variable palette, admin switcher ✅
7. **Plugins** — hook registry (actions/filters/regions) + signals, runtime enable/disable, example plugin ✅
8. **SEO/GEO** *(in progress)* — Open Graph, JSON-LD entity/service schema, sitemap,
   robots.txt with AI-crawler policy, `llms.txt`, hreflang, multilingual, GEO-optimized
   page type (see [SEO & GEO](#seo--geo-generative-engine-optimization)).
   ✅ 8.1 multilingual content (django-parler) + hreflang + language switcher ·
   ✅ 8.2 SEO core (per-content meta/OG/Twitter, canonical, robots, SEO settings) ·
   ✅ 8.3 JSON-LD (Organization, WebSite, Article, Person, BreadcrumbList)
9. Comments, search, recaptcha spam protection
10. Public site rendering + the luxury frontend
11. AI integration — MCP server (FastMCP)
12. Production deployment (VPS + shared hosting) + demo seed data

## SEO & GEO (Generative Engine Optimization)

> **Status: planned for Phase 8.** This section documents the target so it isn't lost.

DjangoPress is **SEO-first and GEO-first**: the goal is not only to rank in Google but to
be **parsed, understood, and cited by AI answer engines** (ChatGPT, Claude, Gemini,
Perplexity, Google AI Overviews) so that when someone asks an assistant for a service you
offer, your site is surfaced as a recommendation.

Getting recommended by an AI engine has two halves. DjangoPress owns the first; the second
is strategy/off-site and is supported by tooling, not a single page:

**1. On-site — what DjangoPress will build (Phase 8), so every page is AI-ingestible:**

- **AI crawler access** — `robots.txt` that explicitly allows the answer-engine bots
  (`GPTBot`, `OAI-SearchBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, `CCBot`),
  configurable per site, plus a clean `sitemap.xml`.
- **`llms.txt` / `llms-full.txt`** — a concise, machine-readable index of the site and its
  key pages/services that LLMs can read directly (as the reference CMS already did).
- **Structured data (JSON-LD)** — `Organization`, `LocalBusiness`, `Service`, `Product`,
  `FAQPage`, `Article`, `BreadcrumbList`, `Person` (author/E-E-A-T). This is how engines
  extract *which services you provide* and attach them to your entity.
- **A GEO-optimized "Service" page type** — a first-class template that pairs a service
  description with `Service` + `FAQPage` schema, crisp definitional sentences, Q&A blocks,
  pricing/area-served fields, and citable facts — the format answer engines quote verbatim.
- **Semantic, fast, server-rendered HTML** — correct heading hierarchy, canonical URLs,
  Open Graph/Twitter cards, hreflang for multilingual, and quick first-byte (no JS needed
  to read content), because engines reward extractable, fast pages.
- **Citable content patterns** — clear answers near the top, stats, FAQs, last-updated
  dates, and author identity to build the trust signals engines weigh.

**2. Off-site — what actually earns the recommendation (strategy, not a page):**

AI engines recommend brands they encounter repeatedly on sources they trust (reviews,
directories, comparison articles, Reddit/forums, reputable publications). On-site GEO makes
you *eligible and quotable*; visibility comes from being cited across the open web for your
service + location. This is a content-and-outreach program, measured by checking whether the
assistants actually cite you — handled by a dedicated **SEO/GEO strategy** workflow that
audits a specific live site, measures baseline AI visibility, and returns a prioritized plan.

## License

See [LICENSE](LICENSE).
