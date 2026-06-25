# CLAUDE.md

This file guides Claude Code (CLI / VSCode extension) when working in this repository.

## Project

Cmstack-Django is an open-source CMS built on Python/Django. Goal: same
core capabilities as a popular CMS, but lighter, faster, SEO-first, and easy to read,
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
- Publish scheduled content (cron, e.g. every minute): `python manage.py publish_scheduled`
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
    **Public author pages + self-service profile (F10):** the User carries
    `avatar`/`bio`/`website`; `User.get_absolute_url()` → `/authors/<id>/`, a public
    (i18n) archive (`AuthorDetailView` → `accounts.services` →
    `PostRepository.published_by_author`) showing bio/avatar/website + the author's
    published posts. It is gated to users with ≥1 published post so subscriber
    accounts can't be enumerated, and **never renders email**. It emits
    `ProfilePage`+`Person` JSON-LD (`seo.jsonld.profilepage_schema`, the `"profile"`
    branch of `seo_jsonld`). `/account/` (`ProfileUpdateView`, LoginRequired) is the
    self-service editor (name/bio/website/avatar) — `accounts/urls.py` is mounted in
    `i18n_patterns` with namespace `accounts` (`accounts:author_detail`,
    `accounts:profile`); the public header shows an "Account" link when signed in.
  - `apps.content` — posts, pages, categories (hierarchical), tags, and per-type
    revisions. Rich-text bodies are sanitized server-side with nh3 on every save
    (`apps/content/utils.py`); templates render bodies with `|safe` because they
    were cleaned at write time — keep it that way. `publish_post` is a custom
    permission; published querysets via `Model.objects.published()`.
    **Soft-delete (F6):** Post + Page mix in `SoftDeleteModel` (`deleted_at` +
    `trash()`/`restore()`/`is_trashed`) and use `SoftDeleteManager`, whose default
    `get_queryset()` hides trashed rows — so EVERY existing public/admin/search/
    sitemap/feed query excludes trash with no change; trash views opt back in via
    `Model.objects.with_trashed()`/`only_trashed()`. The dashboard "delete" now
    trashes; a Trash list offers restore + permanent-delete (gated on
    `delete_post`/`delete_page`, owner-scoped through `editable_by`). `trash()`/
    `restore()` persist only `deleted_at` via `update_fields`, so the heavy `save()`
    override and the revision-snapshot signal stay no-ops. **Likes (F6):** `Like`
    (post+user, unique together) is a toggle (create = like, delete = unlike) via
    `content:post_like` (login-required; guests redirect to login); the post-detail
    like button is `aria-pressed`-driven and degrades without JS (plain POST form).
    **Revision restore (F7):** snapshots already accrue via `content/signals.py`;
    the dashboard adds a shared revisions page (`dashboard/revisions.html`) with a
    per-language history list, a `difflib` line diff (revision vs current) and a
    restore action. Restore is a model transition (`Post/Page.restore_revision`,
    keeping the service ORM-free); saving re-snapshots so history is preserved, not
    rewritten. Owner-scoped (posts via `editable_by`), gated on `change_post`/
    `change_page`; reachable from a "Revision history" link in each editor.
    **Scheduled publishing (F8):** `SchedulableMixin` adds `scheduled_at` +
    `is_scheduled` + a `publish_scheduled()` transition to Post/Page/Service. A
    scheduled item stays DRAFT (invisible publicly) until its time; the
    `publish_scheduled` management command (run from cron) calls
    `content.services.publish_scheduled_content()`, which flips each
    `Model.objects.due_for_publish()` item via its own transition (no ORM in the
    service) and stamps the scheduled time as `published_at`. The dashboard forms
    expose a datetime-local `scheduled_at` (posts gate it on `can_publish`, like
    status); the post list shows a "Scheduled · <time>" badge.
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
    admin uses `parler.admin.TranslatableAdmin`. **Service (Phase 8.5)** is a
    GEO-optimized content type (translatable, SeoFieldsMixin): `summary`
    (definitional sentence), rich `description` (nh3-sanitized), `price`,
    `area_served`, and a `faq` Q&A textarea (`faq_items()` parses `Q:`/`A:` lines).
    Public at `/services/` + `/services/<slug>/`, dashboard CRUD gated by
    `content.*_service` (Admin/Editor); emits `Service` + `FAQPage` JSON-LD and is
    included in the sitemap + llms.txt.
  - `apps.media` — media library. `MediaAsset` stores files plus extracted metadata
    and a Pillow thumbnail (built on first save). Uploads validated in `forms.py`
    (allowed types in `constants.py`; SVG rejected as an XSS vector). Browse/upload/
    delete views are permission-gated (`media.*_mediaasset`). Files served at
    `/media/` (Django in dev, web server in prod). **In-editor picker (F11):** the
    post/page/service editors mix in `MediaPickerContextMixin`, which feeds recent
    library images (`MediaRepository.images`) to a focus-trapped Alpine modal
    (`dashboard/_media_picker.html`) — shown only to users with
    `media.view_mediaasset`. Picking an image inserts `<img src alt>` into Trix via
    `window.cmstackInsertImage` (`frontend/src/admin.js`); nh3 keeps `img` on save.
    **Swappable storage (F11):** `config.storages.build_storages(env)` builds Django
    `STORAGES` — local disk by default, or an S3-compatible bucket when
    `USE_S3_MEDIA=1` (`storages.backends.s3.S3Storage`; `endpoint_url` covers
    MinIO/R2). Every `FileField`/`ImageField` (media, avatars, OG/featured images)
    follows the `default` storage, so the swap needs no model change. Optional dep
    `django-storages[s3]` is in `requirements/prod.txt`.
  - `apps.dashboard` — the custom admin panel (own UI, NOT the
    Django admin), mounted at `/dashboard/`. Every view extends `AdminAccessMixin`
    (login + `accounts.access_admin`) plus a per-view permission tuple. Posts use
    a Trix editor (`frontend/src/admin.js`, a separate Vite entry) whose HTML is
    sanitized by the content layer on save. Authors/Contributors are scoped to
    their own posts (`PostScopeMixin`); publishing is gated on `content.publish_post`.
  - `apps.core` also holds `SiteSettings` (a cached singleton) exposed to all
    templates as `site` via a context processor, and the public **landing page**
    (`HomeView` → `core/home.html`, Phase 10.2): an editorial hero + feature bento +
    a "From the blog" section that renders the CMS's OWN recent published posts
    (`recent_posts`) + a theme-palette showcase + CTA. It extends `base.html`
    directly (full-bleed sections) and shares the nav/footer with the content shell
    via the `_site_header.html` / `_site_footer.html` partials; `<head>` extras
    (theme palette + hreflang) come from `_public_head.html`. **The shell lives in
    ONE place — header, footer, and public-head are partials included by BOTH
    `public_base.html` and the landing, so the two can never drift** (the same
    lesson as the theme refactor). Don't override `extra_head` on a public page
    without re-including `_public_head.html`, or you drop the palette + hreflang.
  - `apps.themes` — swappable themes resolved at runtime. Themes live in the
    top-level `themes/<slug>/` (a `theme.json` + optional `templates/`). The
    `ThemeLoader` (in `OPTIONS.loaders`, ahead of filesystem/app loaders; note
    `APP_DIRS` is therefore `False`) resolves the active theme's templates first,
    dynamically per render (no restart to switch). Active theme = `SiteSettings.
active_theme`, changed under Dashboard → Appearance (`manage_settings`). The
    palette is CSS variables (`--color-paper/ink/accent`; default values in
    `styles.css` `:root`). **A theme recolors the site by overriding ONLY those
    variables via a `_theme_palette.html` include — it does NOT fork the shell**
    (Phase 10.1): the shared `templates/public_base.html` does
    `{% include "_theme_palette.html" %}` in `extra_head`; the active theme's
    `themes/<slug>/templates/_theme_palette.html` (resolved first by `ThemeLoader`)
    emits its `<style>:root{…}</style>`, while the default theme ships none so the
    empty project-level include renders and the `styles.css` default applies. So
    `themes/midnight` is palette-only (a 6-line file) and automatically inherits
    every shell change (nav/search/language switcher) — it can't drift. Tailwind
    scans `themes/` (see `tailwind.config.js` + the Dockerfile COPY).
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
    **Crawler surface (8.4):** `sitemaps.py` (Post/Page/Static, `i18n=True`+
    `alternates=True` → hreflang in the sitemap; excludes drafts + `noindex`) at
    `/sitemap.xml`; dynamic `/robots.txt`, `/llms.txt`, `/llms-full.txt` views
    (`apps/seo/views.py`, wired at the root in `config/urls.py`, outside i18n).
    robots.txt disallows private paths and emits an explicit per-bot allow/deny
    policy for answer-engine crawlers (`constants.AI_CRAWLER_USER_AGENTS`, toggled by
    `SeoSettings.allow_ai_crawlers`); `discourage_search` short-circuits to
    `Disallow: /` with no sitemap. llms.txt files capped at `LLMS_MAX_ITEMS`. NOTE:
    `sitemap.xml` `<loc>` uses the `django.contrib.sites` domain (set the Site to the
    real domain in prod — Phase 12); robots/llms use the request host. **Service +
    FAQPage JSON-LD (8.5):** `jsonld.service_schema`/`faqpage_schema`; the
    `seo_jsonld` tag's `"service"` branch emits Service+FAQPage+BreadcrumbList. A
    freeform `price` is deliberately NOT emitted as a schema.org `Offer` (invalid
    without numeric price/currency) — it stays a visible on-page fact.
  - `apps.comments` — threaded, moderated comments on posts (Phase 9). `Comment`
    (post FK, self-FK `parent`, nullable `user`, `name`/`email` for guests, plain-text
    `body`, `status` pending/approved/spam — default pending). Bodies are ALWAYS
    rendered autoescaped (`{{ comment.body }}`, never `|safe`) — markup shows as text,
    so no HTML sanitisation. `moderate_comment` is a custom perm (roles.py already
    grants Admin/Editor the comment perms). Public submission is handled by
    `PostDetailView.post()` (posts to the post's own URL, so the language prefix is
    kept): guests/logged-in both go to `pending`; logged-in identity comes from the
    account (name/email fields are dropped). `CommentForm.parent` queryset is scoped
    to APPROVED comments on the same post, so a reply can't target another post or an
    unmoderated comment. Gated by `SiteSettings.allow_comments` /
    `comments_require_login`. Moderation UI at Dashboard → Comments
    (`CommentListView` + `CommentModerateView`, approve/spam/delete, gated by
    `comments.moderate_comment`). **Spam (9.3, django-recaptcha v3):** an invisible
    `captcha` `ReCaptchaField` is added to `CommentForm` **only when both
    `RECAPTCHA_PUBLIC_KEY` and `RECAPTCHA_PRIVATE_KEY` are set** (`forms.recaptcha_enabled()`,
    read live from settings). Keys come from env (default `""`), so dev/CI/tests run with
    NO captcha and the 9.1 flow is byte-for-byte unchanged. `django_recaptcha` is in
    `INSTALLED_APPS`; the public site key is rendered client-side, the private key stays
    server-side. Empty defaults are NOT the library's built-in test keys, so `manage.py
check` stays clean (0 silenced) — no `SILENCED_SYSTEM_CHECKS` needed.
  - `apps.menus` — managed navigation (F9). `Menu` (referenced by `slug`) +
    `MenuItem` (links a Post/Page/Category or a custom URL; `get_url()`/`get_label()`
    resolve the target, with `label` falling back to the linked object's translated
    title so content links localise automatically). `menus.services.get_menu_items
(slug)` → render-ready `[{label,url}]`; the `{% menu_items "slug" as items %}` tag
    (`menus/templatetags/menu_tags.py`) exposes it. The shared `_site_header.html`
    (`primary`) and `_site_footer.html` (`footer`) render a managed menu when one
    exists and fall back to built-in links otherwise. The admin builder lives in the
    dashboard (manage_settings-gated): create/delete menus, add/edit/delete items,
    and keyboard-accessible up/down reordering (POST that swaps `position` — no
    drag-JS). NOTE (deliberate scope): menus are **flat** and `label` is **not**
    per-locale (the title fallback covers content links) — see REFACTOR_PLAN §7.
  - `apps.api` — public REST API (DRF, F12) at `/api/v1/` (outside i18n). ReadOnly
    viewsets for posts/pages/services/categories/tags (published-only, parler-aware
    serializers, `?lang=` override, list/detail split); the post viewset also takes
    gated writes (`ModelViewSet`): `TokenAuthentication`+`SessionAuthentication`,
    `DjangoModelPermissionsOrAnonReadOnly` (anon read, model-perm-gated write),
    owner-scoped writes, publish gated server-side via `gate_publish_state`.
    Persistence runs through `content.services.api_create_post/api_update_post` →
    repository (no ORM in viewsets/serializers). `manage.py create_api_token <user>`
    mints tokens. `/health/` (liveness) + `/health/ready/` (DB probe) live here too.
  - `apps.mcp` — MCP server (F12) at `POST /api/mcp/` with a `tools/list` +
    `tools/call` JSON surface. `tools.py` is a registry of 13 management tools
    (posts CRUD+publish, pages/categories/tags/media/users lists, comments.moderate,
    settings.get); each declares the permission(s) it needs and the executor
    (`services.call_tool`) **re-verifies them server-side** against the calling user
    before delegating to the existing app services/repositories (same rules as the
    UI). Token/session auth is the auth floor (`IsAuthenticated`). NOTE (deliberate
    scope, REFACTOR_PLAN §7): token auth, not full OAuth 2.1; HTTP-JSON, not an
    SSE/stdio MCP transport — both layer on later without touching the tools.
  - `apps.search` — public site search over published Posts and Pages (Phase 9.2).
    `services.search_content(query, language_code)` is the single entry point: it
    searches the translated title/body (+ Post excerpt) of the **active language's**
    translation row only (`translations__language_code=code`), returns a flat,
    relevance-sorted list of mixed Post/Page instances each carrying `search_rank`,
    `search_type` and a normalised `search_excerpt`. Backend chosen at query time on
    `connection.vendor`: PostgreSQL uses `SearchVector`/`SearchQuery`/`SearchRank`
    (ranked); every other engine (incl. the SQLite test DB — so the fallback is what
    tests exercise) uses a DB-agnostic `icontains` OR-match. Always excludes drafts
    AND `noindex` items (consistent with the sitemap/crawler surface); query capped at
    200 chars (cheap DoS guard). `django.contrib.postgres` is deliberately NOT in
    `INSTALLED_APPS` — the search expressions are plain ORM and work without it
    (verified on Postgres), and adding it would impose postgres-only checks on the
    SQLite test env. Public results page (paginated, `paginate_by=10`) at `/search/?q=`
    (inside `i18n_patterns`, so `/de/search/` works); a search box lives in the
    `public_base.html` header.

Frontend assets: changing anything under `frontend/` and rebuilding requires
`docker compose up -d --build --renew-anon-volumes` (the dev container surfaces the
image's `frontend/dist` through an anonymous volume that otherwise persists stale).
NOTE: CSS files imported by a Vite entry (e.g. `admin.css`) must use plain `@apply`
rules, NOT `@layer`, unless they include their own `@tailwind` directives.

- `frontend/` — Vite + Tailwind + Alpine source; builds to `frontend/dist`
  (with `.vite/manifest.json`), wired into templates via `django-vite`.
  **Type system (DESIGN_SYSTEM convergence):** self-hosted variable fonts via
  Fontsource (`@fontsource-variable/newsreader` = `font-display` serif for
  headings/prose, `inter` = `font-sans` UI body, `geist-mono` = `font-mono`),
  imported in `src/main.js`, bundled by Vite (no CDN), `font-display: swap`.
  Tailwind `fontFamily` maps the three; `h1–h4` + `.dp-prose` get `font-display`.
  **Design tokens:** the full semantic set (`--bg`/`--surface`/`--surface-2`/
  `--text`/`--text-muted`/`--text-subtle`/`--primary`/`--accent`/`--border`/
  `--ring`/state colors) lives on `:root` (light) and `.dark` in `styles.css`,
  bridged into Tailwind (`bg-surface`, `text-muted`, `border-border`, …);
  `darkMode:"class"`. Legacy `paper`/`ink`/`accent` utilities are aliased onto the
  new tokens during the UI migration. Themes re-scope tokens via `_theme_palette.html`. **Motion:** a self-contained scroll-reveal
  primitive — add `class="reveal"` to any element and `src/main.js`'s
  IntersectionObserver fades it in once. Robust by construction: the hidden
  start-state is raw CSS (never purged) gated on BOTH `html.js` (set by main.js)
  AND `prefers-reduced-motion: no-preference`, so no-JS and reduced-motion visitors
  always see fully-rendered content. No per-element directive needed. `.stagger`
  gives direct children a short cascading delay. **Primitives in `styles.css`
  (all raw CSS so dynamic/sanitized markup isn't purged):** `.dp-btn` +
  `.dp-btn-primary`/`.dp-btn-ghost` (press `scale(0.97)`, hover lift gated to real
  pointers, `--ease-out` curve); `.dp-prose` (Phase 10.3 long-form article
  typography for nh3-sanitized post bodies); `.dp-form` (PUBLIC form styling —
  the dashboard's `.dp-form` lives in the separate `admin.css` bundle that public
  pages don't load, so the public comment form needs its own rules here);
  `[x-cloak]` display:none (Alpine). `.dp-auth` styles the allauth screens.
- `templates/` — project-level base templates. `base.html`; `public_base.html`
  (content shell); the public landing extends `base.html` directly. The shell is
  factored into partials shared by both so it can't drift: `_site_header.html`,
  `_site_footer.html`, and `_public_head.html` (theme palette + hreflang). Themes
  override `_theme_palette.html` only.
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
