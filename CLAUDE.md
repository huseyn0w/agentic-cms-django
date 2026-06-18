# CLAUDE.md

This file guides Claude Code (CLI / VSCode extension) when working in this repository.

## Project

DjangoPress is an open-source, WordPress-style CMS built on Python/Django. Goal: same
core capabilities as WordPress, but lighter, faster, SEO-first, and easy to read,
understand, and extend. It is a commercial/open project that will be demoed publicly,
so code quality, security, and a clean demo matter.

Reference implementation by the same author (Laravel, study for feature parity, not for
code style): https://github.com/huseyn0w/Laravella-CMS

## Stack (confirm in the roadmap before building; deviate only with a stated reason)

- Python 3.12, Django 5.x
- PostgreSQL (default). Keep all DB access ORM-level and DB-agnostic so MySQL works for
  shared hosting.
- Tailwind CSS 3 + Alpine.js, bundled with Vite (django-vite).
- Auth/social login: django-allauth. Multilingual: django-parler or django-modeltranslation.
- Spam: django-recaptcha (v3). Rich text editor: a maintained, sanitized editor.
- Tests: pytest + pytest-django. Lint/format: ruff + black. Types: mypy where it pays off.
- Local infra: Docker + docker compose. Prod: gunicorn + nginx + whitenoise on VPS;
  a separate guide for shared hosting (Hostinger / Passenger / cPanel).

## Architecture conventions

- Idiomatic Django, organized as focused Django apps (e.g. accounts, content, media,
  themes, plugins, seo, comments, search, api/mcp). One app = one bounded concern.
- Thin views, logic in model methods and small service functions. Add a repository or
  service layer only where it removes real duplication — do not add it speculatively.
- Themes: swappable template sets resolved at runtime. Plugins: extension points via
  Django signals / a small hook registry, not arbitrary code injection.
- SEO/GEO is a first-class app: Open Graph, JSON-LD, sitemap.xml, robots.txt, hreflang.

## Commands (keep this section updated as the project grows)

- Dev up: `docker compose up`
- Migrate: `docker compose exec web python manage.py migrate`
- Seed demo data: `docker compose exec web python manage.py seed_demo`
- Tests: `docker compose exec web pytest` (single test: `pytest path::test_name`)
- Lint/format: `ruff check .` and `black .`
- Frontend build: `cd frontend && npm run build` (watch: `npm run dev`)
- Lint locally without Docker: `pytest`, `ruff check .`, `black .` from a venv with
  `requirements/dev.txt` installed.

## Project structure (as built)

- `config/` — Django project. Settings are split under `config/settings/`:
  `base.py` (shared, reads env via django-environ), `dev.py`, `prod.py` (hardened),
  `test.py` (in-memory SQLite, no external services). `urls.py`, `wsgi.py`, `asgi.py`.
- `apps/` — one Django app per bounded concern. App label is `apps.<name>`
  (e.g. `apps.core`). New apps: set `name = "apps.<name>"` in their `AppConfig`.
  - `apps.accounts` — custom user (`AUTH_USER_MODEL = "accounts.User"`), roles as
    Django Groups, granular permissions. Default roles + their permissions are
    defined in `apps/accounts/roles.py` and synced idempotently on every
    `post_migrate` (`apps/accounts/signals.py`); the map may reference permissions
    from models that don't exist yet (they're assigned once those phases land).
    Auth/social login via django-allauth, mounted at `/accounts/`.
  - `apps.content` — posts, pages, categories (hierarchical), tags, and per-type
    revisions. Rich-text bodies are sanitized server-side with nh3 on every save
    (`apps/content/utils.py`); templates render bodies with `|safe` because they
    were cleaned at write time — keep it that way. `publish_post` is a custom
    permission; published querysets via `Model.objects.published()`.
    **Multilingual (Phase 8.1, django-parler):** translated fields live on a
    per-model translation table — Post(title/excerpt/body), Page(title/body),
    Category(name/description), Tag(name). `slug`/`status`/`published_at`/`author`/
    taxonomy FKs stay SHARED on the base model (one stable slug per record; the URL
    language prefix differentiates languages), so managers, URLs and publish/scoping
    logic were unaffected. Query translated fields via `Model.objects.language(code)`
    or `filter(translations__field=...)`, NEVER `filter(title=...)` (raises
    FieldError). nh3 still runs in `save()` for EVERY language's body. Revisions
    carry a `language_code` (per-language history). Managers are parler
    `TranslatableManager.from_queryset(PublishableQuerySet)`. Editable through the
    dashboard one language at a time via `?language=xx` tabs; the interim Django
    admin uses `parler.admin.TranslatableAdmin`.
  - `apps.media` — media library. `MediaAsset` stores files plus extracted metadata
    and a Pillow thumbnail (built on first save). Uploads validated in `forms.py`
    (allowed types in `constants.py`; SVG rejected as an XSS vector). Browse/upload/
    delete views are permission-gated (`media.*_mediaasset`). Files served at
    `/media/` (Django in dev, web server in prod).
  - `apps.dashboard` — the custom WordPress-style admin panel (own UI, NOT the
    Django admin), mounted at `/dashboard/`. Every view extends `AdminAccessMixin`
    (login + `accounts.access_admin`) plus a per-view permission tuple. Posts use
    a Trix editor (`frontend/src/admin.js`, a separate Vite entry) whose HTML is
    sanitized by the content layer on save. Authors/Contributors are scoped to
    their own posts (`PostScopeMixin`); publishing is gated on `content.publish_post`.
  - `apps.core` also holds `SiteSettings` (a cached singleton) exposed to all
    templates as `site` via a context processor.
  - `apps.themes` — swappable themes resolved at runtime. Themes live in the
    top-level `themes/<slug>/` (a `theme.json` + optional `templates/`). The
    `ThemeLoader` (in `OPTIONS.loaders`, ahead of filesystem/app loaders; note
    `APP_DIRS` is therefore `False`) resolves the active theme's templates first,
    dynamically per render (no restart to switch). Active theme = `SiteSettings.
    active_theme`, changed under Dashboard → Appearance (`manage_settings`). The
    palette is CSS variables (`--color-paper/ink/accent` in `styles.css`), so a
    theme recolors everything by overriding them in its `public_base.html`.
    Tailwind scans `themes/` (see `tailwind.config.js` + the Dockerfile COPY).
  - `apps.plugins` — the extension system. `hooks.py` is a small registry of
    actions (`do_action`), filters (`apply_filters`), and region renderers
    (`render_hook`, exposed as the `{% hook %}` template tag). Callbacks are
    plugin-scoped (slug inferred from the module under `plugins.`) and skipped
    when that plugin is disabled, so plugins toggle at runtime. Enable state =
    the `Plugin` model, synced on `post_migrate`, switched at Dashboard → Plugins
    (`manage_settings`). Actual plugins live in top-level `plugins/<name>/`
    (Django apps in `INSTALLED_APPS`); `plugins/reading_time` is the example.
    The `post_content` filter is applied in `content/post_detail.html` via the
    `{% post_content post %}` tag; plugin filter output is trusted (operator code).
  - `apps.seo` — the SEO/GEO app (Phase 8). `SeoSettings` is a cached singleton
    (mirrors `SiteSettings`, pk=1) holding OG defaults, GA/GTM IDs, verification
    tags and a site-wide `discourage_search` (noindex) toggle; exposed to templates
    as `seo` via a context processor, editable at Dashboard → SEO (`manage_settings`).
    `SeoFieldsMixin` (plain Python, no DB fields — composes with parler) gives
    Post/Page `seo_title`/`seo_description`/`seo_robots`/`og_image_url` with
    fallbacks. Per-content SEO fields live on the content models: translatable
    `meta_title`/`meta_description` (parler) + shared `canonical_url`/`noindex`/
    `og_image`. The `{% seo_head obj og_type %}` tag (`seo_tags`) computes every
    `<head>` value (title/desc/canonical/robots/OG/Twitter/verification/GA-GTM) and
    renders `templates/seo/head.html`. It's wired through `base.html`'s
    `{% block seo_head %}`: detail templates override it with their object; the
    dashboard base and allauth layout override it to opt OUT (no public meta or
    analytics on private/auth pages). All meta values are operator-supplied and
    autoescaped; GA/GTM IDs are format-validated in `SeoSettingsForm`.
    **JSON-LD (8.3):** `jsonld.py` has pure dict builders (Organization, WebSite,
    Person, Article, BreadcrumbList); the `{% seo_jsonld obj og_type %}` tag
    assembles them (Organization+WebSite everywhere; +Article+BreadcrumbList on
    posts) and serialises each with `_dump_ld` — `json.dumps` then escaping
    `< > &` to `<>&` so a value can't break out of the
    `<script type="application/ld+json">` block (mark_safe is only applied AFTER
    that escaping — keep it). Rendered via a separate `{% block seo_jsonld %}` with
    the same dashboard/allauth opt-out. Organization data comes from `SeoSettings`
    (`organization_logo`, `social_profiles` → `sameAs`, validated http(s) in the form).
    (8.4 sitemap/robots.txt/llms.txt, 8.5 Service page type land here.)

Frontend assets: changing anything under `frontend/` and rebuilding requires
`docker compose up -d --build --renew-anon-volumes` (the dev container surfaces the
image's `frontend/dist` through an anonymous volume that otherwise persists stale).
NOTE: CSS files imported by a Vite entry (e.g. `admin.css`) must use plain `@apply`
rules, NOT `@layer`, unless they include their own `@tailwind` directives.
- `frontend/` — Vite + Tailwind + Alpine source; builds to `frontend/dist`
  (with `.vite/manifest.json`), wired into templates via `django-vite`.
- `templates/` — project-level base templates (`base.html`).
- `docker/` — `entrypoint.sh` (waits for DB, migrates, then runs the CMD).
- `requirements/` — `base.txt`, `dev.txt`, `prod.txt`.

Settings selection: `DJANGO_SETTINGS_MODULE` chooses dev/prod; pytest pins
`config.settings.test` via `--ds` so the container's env var can't override it.
Frontend assets: in dev with the Vite server, set `DJANGO_VITE_DEV_MODE=True` for HMR;
otherwise built assets are served from the manifest (the docker compose default).

Internationalization (Phase 8.1): `LANGUAGES = en, de` (`LANGUAGE_CODE = "en"`, a
bare code so it matches parler's lookups). `PARLER_LANGUAGES` is keyed by `SITE_ID`
(not `None`) — parler's language-tab helper looks it up directly. Public content +
core URLs are wrapped in `i18n_patterns(prefix_default_language=False)` in
`config/urls.py`: the default language keeps clean URLs (`/blog/<slug>/`), other
languages are prefixed (`/de/blog/<slug>/`); `LocaleMiddleware` (after sessions,
before common) activates the language from the prefix. admin/dashboard/accounts/
media stay OUTSIDE the i18n patterns. `apps/core/context_processors.py:i18n_alternates`
builds hreflang/x-default alternates + switcher data via `translate_url`, emitting
them only when the per-language URLs differ (so non-public pages get none); rendered
in `templates/public_base.html`'s `extra_head` + header switcher. Dashboard create/
update views use `DashboardTranslatableFormMixin` (parler `?language=xx`, validated
against `LANGUAGES`) with the `_language_tabs.html` partial. GOTCHA: the root
`conftest.py` resets the active language per test (LocaleMiddleware leaves it
activated, which otherwise makes `reverse()`/URL tests order-dependent).

## Working rules

- Run tests and ruff after every change; a change is not done until both pass.
- Only make changes directly requested or clearly necessary. Do not add extra files,
  abstractions, or configurability that was not asked for.
- Never commit secrets; all config via environment variables (.env, with .env.example).
- Keep README.md and this file current when commands, stack, or structure change.
- Communicate with the user in English.
