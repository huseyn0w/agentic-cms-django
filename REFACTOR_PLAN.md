# cmstack-django — Refactor Plan

> Master plan coordinating the architecture refactor, feature parity, unified UI, and
> test work for `cmstack-django`. Grounded in a code-level audit (not the matrix prose).
> Canon: [`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md), [`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md)
> (read-only). Detailed per-phase TDD plans live under `docs/superpowers/plans/`.

**Status legend:** ☐ pending · ◐ in progress · ☑ done · ⊘ rejected (with reason)

---

## 0. Governing rule (updated 2026-06-24 by the user — supersedes the earlier stance)

The prompt now carries a **non-negotiable, top-priority Hard Rule**: views in
`apps/*/views.py` must contain **ZERO business logic and ZERO data access**. A view's only
job is the HTTP boundary — parse/validate input → call a **service** function → render/
respond. No domain rules, no business-state conditionals, no ORM (`.filter()/.create()/
.save()`/`.count()`/querysets), no `get_object_or_404`, no multi-step orchestration in a
view. All of that moves to `apps/<app>/services.py`, which delegates to custom Managers/
QuerySets for data. This is the single most important acceptance criterion; adversarial
verification MUST reject any view still holding logic or ORM, and we redo until clean.

> **This overrides the original audit conclusion.** The earlier finding (views are "mostly
> already thin") was true relative to *idiomatic Django*, but the user has raised the bar
> above the framework default: even Django's normal `queryset=`/`get_queryset`/`get_object`/
> `form_valid` data-access counts as a defect here. So we DO adopt a full service layer
> across every app — not as speculative abstraction, but as an explicit, user-mandated
> architectural constraint.

### Canonical view↔service pattern (apply uniformly)
- **List:** `def get_queryset(self): return <app>_services.list_<things>(**filters)` — the
  service builds the queryset from managers (`Post.objects.published().select_related(...)`).
  Request parsing (`self.request.GET.get(...)`) stays in the view; the parsed primitives are
  passed to the service.
- **Detail:** `def get_object(self): return <app>_services.get_<thing>_for_view(slug, self.request.user)`
  — the service does the lookup + visibility rule and raises `Http404` on miss/forbidden
  (raising `Http404`/`get_object_or_404` from a service is allowed — it is a not-found signal,
  not business logic).
- **Create/Update:** `form_valid` calls a service that prepares the instance (author, publish
  gating, etc.); the framework's inherited `form.save()` persists (parler-safe). No ORM in our
  view body.
- **Action (POST):** view parses args → calls one service function → flashes/redirects.
- **Context:** any context that needs data comes from a service returning plain values/dicts.
- Singleton loads (`SiteSettings.load()`) are accessed via services, not directly in views.

Services follow the house style (`apps/search/services.py`): module-level `def`, typed
params/returns, primitives in, `_`-prefixed helpers, data access delegated to repositories.

### 0a. Second governing rule (updated 2026-06-24) — repository layer + observer for effects
Non-negotiable, added by the user after the view rule:
- **Services NEVER touch the ORM directly.** No `Model.objects`, `.filter()/.create()/
  .save()/.delete()` inside `services.py`. All data access goes through a **repository**
  (`apps/<app>/repositories.py`) — thin classes/functions over the custom Managers/QuerySets
  that are the single home for ORM calls (queries, create-from-form, delete, bulk).
- **Side effects never run inline in a service.** Notifications, cache invalidation, search
  reindex, audit → the service emits a **domain event / Django signal** and **receivers
  (observers)** in `apps/<app>/signals.py` perform the effect.
- **Layering:** `view → service → repository → manager/QuerySet → model`, plus
  `service → signal → receiver` for effects.
- **What stays a model method:** a model's own state transitions/invariants
  (`Comment.approve()/mark_spam()`, `Post.gate_publish_state()`, `save()` sanitize/slug) are
  legitimate entity behavior, not "raw ORM in a service" — services call these methods rather
  than reimplementing them. Repositories own *queries* and *create/delete* persistence.
- Services fire **no** inline side effects. The first real effect — F5 comment-notification
  email — is implemented through the mandated pattern: `submit_comment` emits the
  `comment_created` domain signal (via `send_robust`), and the observer
  `comments/signals.py::notify_post_author` performs the email. Future effects follow the
  same shape.

Repository rollout status: ☑ content, comments, core, media, search, **dashboard, accounts,
seo** — ALL apps done. Verified: `grep` finds zero ORM in any `views.py` and zero raw
`Model.objects`/`get_object_or_404` in any `services.py`. Full suite **250 passed**, ruff
clean, coverage **95%** overall (services/repositories ≥90% except `search/repositories` 70%
— the PostgreSQL FTS branch is SQLite-untestable; needs a Postgres CI job, see §4).

---

## 1. Architecture refactor (Task 2)

### 1.0 Full per-view refactor scope (Hard Rule §0)
Every view in every app must become an HTTP-boundary shell delegating to a service. Targets
A–E below are the *logic-bearing* extractions (already done ✓); on top of them, **all data
access** in the views of `content`, `dashboard`, `media`, `seo`, `core`, `search` moves into
each app's `services.py`. Status:
- ☑ A–E + comment submission/moderation + `editable_by` + `dashboard_stats` (done, tested).
- ☑ `content` views → `content/services.py` → `content/repositories.py`.
- ☑ `dashboard` views → `dashboard/services.py` → content/comments/accounts/core/seo repos.
- ☑ `media` views → `media/services.py` → `media/repositories.py`.
- ☑ `seo` views → `seo/services.py` → `seo/repositories.py` + content repos.
- ☑ `core` `HomeView` → `core/services.py` → content repos.
- ☑ `search` `SearchView` → `search/services.py` → `search/repositories.py`.
- ☑ `comments` submission/moderation → `comments/services.py` → `comments/repositories.py`.

### 1.1 Existing structure to preserve (do NOT touch)
- `apps/content/models.py` `PublishableQuerySet` / `PublishableManager` — publish rule lives here. ✅
- `apps/comments/models.py` `CommentQuerySet.approved()/pending()`. ✅
- Model methods: `Post/Page/Service.can_be_viewed_by`, `.is_published`, `.save()` invariants. ✅
- Signals: `content/signals.py` (revisions), `media/signals.py` (file cleanup), `accounts/signals.py`, `plugins/signals.py`. ✅
- `apps/search/services.py` — **the house service style** (module-level `def`, typed params/return,
  primitives in, plain data out, `_`-prefixed private helpers). New services copy this style.

### 1.2 Genuine extraction targets (the only refactors we do)

| # | Target (current location) | Chosen pattern | Justification | Rejected alternative |
|---|---|---|---|---|
| A | Owner-scoping rule duplicated in `dashboard/views.py` `PostScopeMixin` (L104–108) **and** `DashboardHomeView` (L87–90) | **Manager/QuerySet method** `Post.objects.editable_by(user)` on `PublishableQuerySet` | Removes real duplication of a *security-relevant* visibility rule; data-access belongs on the manager (consistent with `published()`). | A `services.py` function — rejected: it's a queryset filter, not orchestration; a manager method is the idiomatic home and composes with `select_related`. |
| B | Comment submission blob in `content/views.py` `PostDetailView.post()` (L86–108): gating + identity assignment + save + flash | **Service function** `apps/comments/services.py::submit_comment(post, user, data)` | The single biggest business-logic blob in a public view; mixes auth, identity, persistence — exactly the orchestration `search_content` standardized. Also reused by the future REST/MCP comment-create path (§2). | Leave in view — rejected: not reusable by API/MCP, hard to unit-test in isolation. Model method — rejected: needs form/`data` + request-user policy, which is service-level orchestration, not model state. |
| C | Comment moderation transition table in `dashboard/views.py` `CommentModerateView.post()` (L541–562) | **Model methods** `Comment.approve()` / `Comment.mark_spam()` (+ thin `comments.services.moderate(comment, action)` dispatcher reused by API/MCP) | Status transitions are model state changes; methods pair naturally with `CommentQuerySet`. Dispatcher removes the `_ACTIONS` map from the view and gives API one call site. | Pure service with raw `save(update_fields=...)` — rejected: the state transition is intrinsic to the model; methods read better and are reusable. |
| D | Publish-gating in `dashboard/views.py` `PublishGatingMixin` (L131–151) incl. `.only("status").get()` data peek | **Model method** `Post.gate_publish_state(user)` (encapsulates the "non-publishers can't change status; preserve stored status on edit" rule + the `.only("status")` fetch) | Status-transition policy belongs next to `Post.save()`/`is_published`, not in a view mixin; hides the data peek. The mixin stays but delegates. | Service function — rejected: it mutates a single model instance's state from its own stored value; that's model behavior. |
| E | Cross-app stats rollup in `dashboard/views.py` `DashboardHomeView` (L80–85) | **Service function** `apps/dashboard/services.py::dashboard_stats()` | The only place several apps' counts are assembled together — genuine cross-app orchestration; isolates 4 `.count()` calls for testing/caching. | Leave inline — borderline; extracted because it's cross-app and the home view also uses target A (`editable_by`), so the view becomes a clean parse→call→render. |

### 1.3 Patterns explicitly NOT introduced (and why)
- **Repository pattern (separate class):** Django's Manager/QuerySet *is* the repository. A
  parallel `FooRepository` would duplicate it. ⊘
- **DRF serializers/viewsets:** deferred to §2 (REST API feature) — only added when the API
  surface is actually built, not retrofitted onto the current server-rendered views. ◐
- **Factory/Strategy/Adapter/Bridge:** the one real branch (search backend: Postgres FTS vs
  `icontains`) already uses a clean `_is_postgres()` strategy inside the service. The future
  **storage driver** (§2) is the one place a Strategy/Adapter genuinely pays off (local ↔ S3)
  — introduced there via Django's `STORAGES` setting, not a bespoke class hierarchy. ☑ DONE
  (F11: `config.storages.build_storages(env)`; env-driven, no class hierarchy).
- **New middleware:** auth/tenancy/locale middleware already present; no new cross-cutting
  concern identified. Rate limiting for comment submit is a feature (§2), done via a small
  service/cache check, not new middleware unless reused. ⊘
- **Signal extraction for cache/sanitize/publish-stamp:** these are intentionally co-located
  in `save()`/singleton `save()`; moving them to signals adds indirection for no gain. ⊘

### 1.4 Refactor execution order (TDD, characterization-first)
1. ☐ Characterization tests pinning current behavior of A–E (capture exact responses, query
   counts via `assertNumQueries`, messages) **before** touching code.
2. ☐ Target A — `editable_by` manager method; rewire `PostScopeMixin` + `DashboardHomeView`.
3. ☐ Target B — `submit_comment` service; `PostDetailView.post()` becomes parse→call→respond.
4. ☐ Target C — `Comment.approve()/mark_spam()` + `moderate()`; rewire `CommentModerateView`.
5. ☐ Target D — `Post.gate_publish_state(user)`; `PublishGatingMixin` delegates.
6. ☐ Target E — `dashboard_stats()`; rewire `DashboardHomeView`.
7. ☐ Adversarial verification: 2–3 independent skeptics per target (behavior-preservation /
   security / N+1). Fix until majority cannot break it.

### 1.5 Acceptance for Task 2
- No business logic or direct ORM in the 5 target views beyond parse→call→render.
- All pre-existing tests still pass; characterization tests green; no new N+1 (assertNumQueries).
- Each extraction reused by at least the view it came from (and API/MCP where noted).

---

## 2. Feature parity (Task 1) — verified gaps vs canon

Every matrix claim for django was **verified accurate** against code (no matrix errors found;
if one surfaces later, record it here and flag — do NOT edit the shared file). Ordered by
value/risk. Effort: S/M/L from audit.

| # | Feature | Status | Effort | Notes / canonical source |
|---|---|---|---|---|
| F1 | Search includes **services** | partial | S | `search_content` only does Post+Page; add Service. Quick win, pairs with §1. |
| F2 | **Coverage** measured (pytest-cov + `fail_under`) | absent | S | Required to verify Task 4 targets at all. Do early. |
| F3 | **RSS feed** (`/rss.xml`) | ☑ DONE | S | `LatestPostsFeed` (`content/feeds.py`) via `PostRepository.for_feed`; wired at root + `<link rel=alternate>` autodiscovery in `_public_head`. 3 tests. (Per-category feeds: optional follow-up.) |
| F4 | **Contact form** + email | ☑ DONE | S–M | `/contact/` email-only (no model): `ContactForm` (reCAPTCHA-graceful) → `core.services.submit_contact` → `contact_received` signal → observer emails `settings.CONTACT_EMAIL` (env-driven, no-op if blank, reply-to sender). Footer link added. 4 tests. |
| F5 | **Comment-notification email** | ☑ DONE | S | `comment_created` domain signal emitted by `submit_comment`; observer `notify_post_author` in `comments/signals.py` emails the post author (send_robust + fail_silently — never breaks submission). Demonstrates the service→signal→observer rule. 4 tests. |
| F6 | **Soft-delete/trash/restore** (posts+pages) + **post likes** | ☑ DONE | M | `SoftDeleteModel` mixin (`deleted_at` + `trash()`/`restore()`/`is_trashed`) + `SoftDeleteManager` (default hides trashed; `with_trashed()`/`only_trashed()`) on Post+Page → every public/admin/search/sitemap query excludes trash automatically. Dashboard delete now trashes; trash list + restore + permanent-delete (delete-perm gated, owner-scoped via `editable_by`). `Like` model (unique post+user, toggle = create/delete) → `content:post_like` endpoint (login-required, redirect-to-login for guests) + a11y like button (`aria-pressed`) on post detail. 21 tests. |
| F7 | **Revision restore UI** (storage exists, restore absent) | ☑ DONE | M | `RevisionRepository` (history list + lookup) + dashboard revisions page (`dashboard/revisions.html`, shared by posts+pages): per-language history sidebar + line-level diff (`difflib`, revision vs current) + restore. Restore is a model transition (`Post/Page.restore_revision`) so the service stays ORM-free; saving re-snapshots so history is preserved. Owner-scoped (posts via `editable_by`), gated on `change_post`/`change_page`. "Revision history" link in both editors. 7 tests. |
| F8 | **Scheduled publishing** (`scheduled_at` + worker) | ☑ DONE | M | `SchedulableMixin` (`scheduled_at` + `is_scheduled` + `publish_scheduled()` transition) on Post/Page/Service; `PublishableQuerySet.due_for_publish()` (draft + due, trashed excluded via default mgr). `content.services.publish_scheduled_content()` flips each due item via its transition (no ORM in service) → `manage.py publish_scheduled` cron command. Dashboard: datetime-local `scheduled_at` field on post/page/service forms (post gated on `can_publish` like status); "Scheduled · <time>" badge in the post list. 9 tests. |
| F9 | **Menu builder** + public menu rendering | ☑ DONE | M | New `apps.menus` (`Menu` slug + `MenuItem` linking post/page/category/custom URL; `get_url()`/`get_label()` with localised title fallback). Dashboard builder (manage_settings-gated): create/delete menus, add/edit/delete items, keyboard-accessible up/down reorder (POST swap, no drag-JS). `{% menu_items "slug" as items %}` tag + `menus.services.get_menu_items` resolve to render-ready dicts; the shared header (`primary`) + footer (`footer`) render managed menus when present, else fall back to built-in links. 14 tests. **Scope note: flat menus + non-translatable label (see §7).** |
| F10 | **Author public pages** + **self-service profile edit** | ☑ DONE | M | Public `/authors/<id>/` (i18n) archive — bio + avatar + website + their published posts; gated to users with ≥1 published post so subscriber accounts aren't enumerable; **email never rendered**. `ProfilePage`+`Person` JSON-LD (`jsonld.profilepage_schema`, new `"profile"` branch in `seo_jsonld`; bio→description, website→sameAs, avatar→image). Self-service `/account/` (LoginRequired) edits name/bio/website/avatar. `User.get_absolute_url()`; post-detail author name links to the archive; header gains an "Account" link. view→service→repository (`accounts.services` → `PostRepository.published_by_author`). 13 tests. |
| F11 | **Media picker in editor** + **swappable storage driver** | ☑ DONE | M | **Picker:** `MediaPickerContextMixin` feeds recent library images (`MediaRepository.images`) to the post/page/service editors (only for users with `media.view_mediaasset`); an accessible Alpine modal (`_media_picker.html`, focus-trapped) inserts `<img>` into Trix via `window.cmstackInsertImage` (admin.js) — survives nh3 (img src/alt allowed). **Storage:** `config.storages.build_storages(env)` selects local disk by default or S3-compatible (`USE_S3_MEDIA=1` → `storages.backends.s3.S3Storage`, MinIO/R2 via endpoint_url) — every FileField/ImageField moves with no model change (Strategy via Django `STORAGES`). `django-storages[s3]` in prod reqs; `.env.example` documented. 9 tests. |
| F12 | **Public REST API** + **MCP server** | ☑ DONE | L | ☑ **F12a read API** (DRF; new `apps.api`: ReadOnly viewsets for posts/pages/services/categories/tags at `/api/v1/`, parler-aware serializers, `?lang=` override, published-only, list/detail split; `/health/` + `/health/ready/` DB probe; viewsets delegate to `api.services`→content repos; 12 tests). ☑ **F12b gated write API** (Post CRUD via `ModelViewSet`; `TokenAuthentication`+`SessionAuthentication`; `DjangoModelPermissionsOrAnonReadOnly` → anon read, model-perm-gated write; owner-scoped writes via `editable_posts`; publish gated server-side (`gate_publish_state`) so the API can't bypass it; persistence via `content.services.api_create_post/api_update_post`→repository; `manage.py create_api_token <user>`; 12 tests). ☑ **F12c MCP server** (new `apps.mcp`: 13-tool registry — posts list/get/create/update/publish/delete, pages/categories/tags/media/users lists, comments.moderate, settings.get — at `POST /api/mcp/` with `tools/list`+`tools/call`; token/session auth floor + **every tool re-verifies its own permission(s) server-side** before delegating to the existing services/repositories; 18 tests). **Auth-floor scope note: token auth, not full OAuth 2.1 — see §7.** |
| F13 | **CI pipeline** | absent | S | GitHub Actions: ruff→black→mypy→pytest(+cov)→build. |
| F14 | **E2E tests** (Playwright) | absent | L | auth+content+SEO+theme journeys. |
| F15 | mypy `django-stubs` plugin not wired | partial | S | enable `mypy_django_plugin.main`. |

Do not silently drop existing features (parler i18n, plugins, themes, GEO/llms, GA4/GTM —
GA4/GTM is already done; keep).

---

## 3. Unified luxury UI (Task 3) — convergence to DESIGN_SYSTEM

Foundational gap: the project ships **Space Grotesk + Geist** and **3 ad-hoc tokens**
(`--color-paper/ink/accent`); the canon mandates **Newsreader + Inter + Geist Mono** and a
**~20-token semantic system + `.dark`**. Every downstream component issue (pill buttons,
off-token badges, no focus ring, ad-hoc cards) traces to the missing token layer.

| # | Area | Effort | Work |
|---|---|---|---|
| U1 | **Token system** | L | ☑ DONE — full §2 semantic set on `:root` + `.dark` in `styles.css`; bridged into Tailwind `theme.extend` (`bg`/`surface`/`text-muted`/`primary`/`border`/`ring`/semantic state colors + `highlight`); legacy `paper`/`ink`/`accent` aliased onto new tokens so templates didn't break; midnight theme palette + radius tokens updated; `darkMode:"class"` set. (Remaining: migrate template utilities to semantic names + wire a dark toggle in U3/U4.) |
| U2 | **Fonts** | L | ☑ DONE — Fontsource swapped to **Newsreader** (display/prose) + **Inter** (UI) + **Geist Mono**; `main.js` imports + Tailwind families + `.dp-prose` serif updated; Vite build verified (main.css 6.7KB gz, main.js 16.7KB gz — within budget). (Remaining: `<link rel=preload>` 2 critical weights + subset → U7 perf.) |
| U3 | **Public UI** | M | Sticky 64px header + scroll-shadow + mobile drawer (focus-trapped); button variants (md radius, not pills); prose → Newsreader; footer/locale switcher on tokens; skip-to-content link. |
| U4 | **Admin UI** | M | Sidebar active = surface-2 + 2px primary bar + mono group labels; topbar dark/light toggle + avatar dropdown; messages → semantic Alert/banner. |
| U5 | **Missing components** | L | Breadcrumbs, dropdown/menu, avatar, file dropzone, sortable list, modals (focus-trap), toasts, alerts, table bulk-select, empty states, conformant badges, rich-text toolbar+aria. |
| U6 | **A11y** | M | ARIA pass (almost none today): `aria-current/pressed/expanded/selected/live/invalid/describedby`; locale tabs `role=tab`/`tabpanel`; pagination `nav`+`aria-current`; focus rings (2px `--ring`); reduced-motion (already partly present). |
| U7 | **Perf / Lighthouse ≥95** | M | Measure with real run (don't assume); subset/preload fonts; verify JS≤40KB/CSS≤40KB; responsive `srcset`+`width/height`+lazy; cache public pages. Show real Lighthouse numbers. |

---

## 4. Tests (Task 4)
- F2 coverage tooling first (can't verify targets otherwise).
- Characterization tests for §1 refactors (before code).
- ≥80% line coverage on services/managers; 100% on critical paths (auth, content CRUD,
  publishing, media, search). Postgres FTS branch currently untested (SQLite tests only) —
  add a Postgres job in CI (§F13) to exercise it.
- Regression test for every bug adversarial verification surfaces.
- factory_boy where it reduces ad-hoc ORM setup.
- Always show real `pytest --cov` output; never claim passing without the run.

## 5. README (Task 5)
Rewrite after the above lands: what it is, architecture (apps + layers + the 5 patterns
actually used, with the "no speculative abstraction" stance stated), setup/run, test+coverage
commands, links to shared specs. Structurally aligned with the other two READMEs.

---

## 6. Phasing (so each session ships working software)

- **Phase 1 (this session):** REFACTOR_PLAN + HANDOFF; F2 coverage tooling; §1 architecture
  refactor (A–E) with characterization tests + adversarial verification; F1 search-services
  (small, pairs with §1). All tests green with coverage shown.
- **Phase 2:** UI foundation U1 (tokens) + U2 (fonts) + U3/U4 shell — the highest-visibility,
  highest-leverage convergence; Lighthouse baseline (U7).
- **Phase 3:** Feature parity wave 1 (S/M): F3 RSS, F5 comment email, F4 contact, F6 soft-
  delete+likes, F7 revision restore, F8 scheduled publish, F9 menus, F10 authors/profile.
- **Phase 4:** F11 media picker+storage, F12 REST API + MCP (largest), U5 remaining components.
- **Phase 5:** F13 CI, F14 E2E, U6 a11y verification, U7 Lighthouse ≥95 proof, F15 mypy plugin;
  README (Task 5); completeness-critic pass.

Each phase: TDD, subagent-driven where parallelizable, adversarial verification before done.

---

## 7. Matrix-gap flags for the user — ALL deferred scope now CLOSED
Every reduction previously flagged here has since been delivered (see the per-feature notes).
No outstanding matrix gaps remain.

- **F9 menus — FULL scope delivered (reduction CLOSED).** The matrix's menu row asked for
  "items reference posts/pages/categories/custom URLs; **per-locale**" with a nested,
  drag-sortable builder. All of it ships:
  - **Arbitrary-depth nested dropdown menus** — `MenuItem.parent` self-FK to ANY depth; the
    public header renders accessible recursive flyout submenus (`_menu_node.html` + the
    `.nav-group`/`.nav-submenu` raw-CSS primitive: reveals on hover **and** `:focus-within`,
    works with **no JS**, `aria-haspopup` + `role=menu`); mobile drawer indents the tree; footer
    flattens it. `get_menu_items` resolves a recursive `[{label,url,children}]` tree assembled in
    Python from ONE flat fetch + translations prefetch (no N+1 at any depth — assertNumQueries
    test). The builder offers a parent select scoped to the menu and **cycle-protected** (never
    self/descendant, enforced in the queryset AND `clean()`), a depth-indented tree view, and
    sibling-scoped reorder.
  - **Drag-and-drop reorder** — SortableJS progressive enhancement in the dashboard builder
    (drops kept sibling-scoped) → JSON `MenuItemReorderView` (HTTP boundary → service →
    `repository.reorder`, `manage_settings`-gated). The keyboard ↑/↓ arrows remain the **no-JS**
    fallback.
  - **Per-locale labels** — `MenuItem.label` is a parler translated field (like
    Post/Page/Category/Tag), edited per language via the dashboard `?language=` tabs;
    `get_label()` resolves active-language label → any translated label → linked object's
    translated title → custom URL. Data-preserving migration (rename→create→copy→drop, verified
    an existing label round-trips into the default-language translation, reverse round-trips too).
- **F12 MCP/API — OAuth 2.1 + SSE delivered (reduction CLOSED).** On top of the existing
  token/session floor + per-tool server-side permission re-verification:
  - **OAuth 2.1 auth floor** via `django-oauth-toolkit` (PKCE required; `read`/`write` scopes;
    provider at `/oauth/`). `OAuth2Authentication` is added ALONGSIDE token+session on the API
    and MCP — OAuth is **authentication only**: DjangoModelPermissions, owner-scoping and the
    per-tool `has_perm` re-verification all still apply (adversarially verified — no authz
    bypass). The API write surface adds an additive scope floor; **MCP scope is per-TOOL** (each
    `Tool.write` flag; a `read`-scope or empty-scope OAuth token cannot run a write tool over
    JSON or SSE), while token/session auth stays un-scoped.
  - **Three transports, one registry + authz:** `POST /api/mcp/` (JSON), `GET /api/mcp/sse`
    (`text/event-stream` — emits `tools/list` on connect and a `tools/call` result event,
    anonymous rejected), and **stdio** (`manage.py mcp_stdio --user <name>` — line-delimited
    JSON-RPC 2.0 over stdin/stdout for local desktop clients; runs as the named user so
    `call_tool`'s per-tool `has_perm` is the authorization; no bearer token so not scope-gated).
  - Nothing left deferred for F12 — all transports + the OAuth floor are delivered.

---

## 8. Per-layer test-status (Task 4) — every layer covered, none at zero

Verified against the suite (**452 unit/integration passed, 10 e2e passed**; coverage ~97%).
Each architectural layer has dedicated and/or transitive tests — none is at zero. Where a
layer is exercised transitively (e.g. repositories through their services), that is noted.

| Layer | Status | Representative tests |
|---|---|---|
| **Models / managers / querysets** | ☑ covered | `content/tests/test_models.py`, `test_managers.py`, `test_soft_delete.py`, `test_scheduled.py`, `test_likes.py`; `comments/tests/test_comments.py`; `media/tests/test_models.py`; `menus/tests/test_models.py`; `accounts/tests/test_models.py` |
| **Views (HTTP boundary)** | ☑ covered | `content/tests/test_views.py` (+ `test_post_list_has_no_n_plus_one` query guard); `media/tests/test_views.py`; `dashboard/tests/test_posts.py`, `test_access.py`, `test_other_crud.py`, `test_trash.py`; `core/tests/test_home.py`, `test_contact.py`; `search/tests/test_search.py`; `accounts/tests/test_authors.py`, `test_profile.py`; `seo/tests/test_crawler_surface.py`; `api/tests/test_read_api.py`, `test_write_api.py`; `mcp/tests/test_mcp.py`; + `tests/e2e` browser journeys |
| **Forms / serializers** | ☑ covered | `media/tests/test_forms.py` (upload validation); `comments/tests/test_recaptcha.py` (conditional captcha field); dashboard form behaviour in `dashboard/tests/test_posts.py`, `test_scheduled.py`, `test_seo.py`; DRF serializers via `api/tests/test_read_api.py` (parler-aware, `?lang=`) |
| **Permissions** | ☑ covered | `content/tests/test_permissions.py`; `media/tests/test_permissions.py`; `dashboard/tests/test_access.py`; `accounts/tests/test_roles.py`; per-tool re-verification in `mcp/tests/test_mcp.py`; model-perm-gated writes in `api/tests/test_write_api.py` |
| **Repositories** | ☑ covered (mostly transitive) | Exercised through their services: `content/tests/test_services.py`, `comments/tests/test_services.py`, `core/tests/test_services.py`, `dashboard/tests/test_services.py`, `media/tests/test_services.py`; `search/tests/test_search.py` drives `search/repositories` (the **Postgres FTS branch is covered only by the Postgres CI job** — SQLite tests hit the `icontains` fallback) |
| **Services** | ☑ covered | `content/tests/test_services.py`, `comments/tests/test_services.py`, `core/tests/test_services.py`, `dashboard/tests/test_services.py`, `media/tests/test_services.py`, `search/tests/test_search.py`; `api.services` via `api/tests/*`; `mcp.services` via `mcp/tests/test_mcp.py` |
| **Signals / receivers (observers)** | ☑ covered | `comments/tests/test_notifications.py` (`comment_created`→email); `core/tests/test_contact.py` (`contact_received`→email); revision-snapshot signal via `dashboard/tests/test_revisions.py` + `content/tests/test_models.py`; media file-cleanup signal via `media/tests/test_models.py`/`test_storage.py`; role sync (`post_migrate`) via `accounts/tests/test_roles.py`; plugin hook side effect via `plugins/tests/test_effect.py` |
| **Templates** | ☑ covered | Rendered-and-asserted in view tests (`content/tests/test_views.py` prose/breadcrumb/chrome; `dashboard/tests/test_a11y.py`; `themes/tests/test_loader.py`; `seo/tests/test_seo.py`, `test_jsonld.py`) + real-browser rendering in `tests/e2e` |
| **Template tags** | ☑ covered | `{% hook %}`/`post_content` in `plugins/tests/test_hooks.py`; `{% menu_items %}` in `menus/tests/test_public.py`, `test_models.py`; `seo_head`/`seo_jsonld` via rendered-page assertions in `seo/tests/test_seo.py`, `test_jsonld.py`; `aria_field` (incl. the new `data-testid` path) in `dashboard/tests/test_a11y.py` + the e2e form journeys |
| **Management commands** | ☑ covered | `publish_scheduled` via `content/tests/test_scheduled.py` (`call_command`); `create_api_token` via `api/tests/test_write_api.py` (`call_command`) |
| **Factories** | ☑ covered (new) | `tests/factories.py` (`UserFactory`, `PostFactory`) + `tests/test_factories.py` smoke tests; consumed by the `content` no-N+1 guard. (Previously zero — `factory_boy` was a declared but unused dev dependency; now wired and exercised.) |

**No-N+1 regression guard (prompt §test, optional item — now done):**
`content/tests/test_views.py::test_post_list_has_no_n_plus_one` warms the cached singletons,
then asserts the public blog index issues the **same** number of queries for 2 vs 6 posts —
locking in the parler-translation + author prefetch so a future change can't reintroduce an
N+1 on the hottest public list view.

---

## 9. Per-event sync/async classification (architecture rule 2 — observer effects)

Both real side effects in the system are notification emails, emitted by a **service** as a
Django `Signal` and performed by a **receiver/observer** in `apps/<app>/signals.py`. Neither
runs inline in its service, and neither is part of the triggering DB transaction.

| Event (signal) | Emitter (service) | Observer (receiver) | Classification | Atomicity | Failure isolation |
|---|---|---|---|---|---|
| `comment_created` | `comments.services.submit_comment` (after the comment is persisted) | `comments/signals.py::notify_post_author` → `send_mail` to the post author | **Async / fire-and-forget** (best-effort notification) | **Non-atomic** — the comment is already saved; the email is decoupled and never gates submission | Emitted via `send_robust` (a dead observer can't break the request) **and** `send_mail(..., fail_silently=True)` |
| `contact_received` | `core.services.submit_contact` | `core/signals.py::email_contact_message` → `EmailMessage.send` to `settings.CONTACT_EMAIL` (no-op if unset) | **Async / fire-and-forget** (best-effort delivery) | **Non-atomic** — there is no contact model; the email is the entire effect and is decoupled from request success | `EmailMessage.send(fail_silently=True)` |

**Notes.**
- "Async" here means **fire-and-forget / failure-isolated / decoupled-via-observer**, not
  out-of-process. There is **no message broker** today, so the receiver currently executes
  **synchronously within the request thread** — but it is explicitly best-effort and swallows
  all failures, so it never blocks or breaks the user-facing action.
- **None of the effects are atomic** with the originating write (and none should be — a mail
  outage must not roll back a comment or a contact submission).
- **Upgrade path (drop-in):** because each effect is already an isolated observer behind a
  signal, moving it onto a real out-of-band worker (Celery/RQ, or `transaction.on_commit` +
  a task queue) is a change to the receiver alone — no service, view, or model is touched.
- Effects that are deliberately **kept inline** (not observers) are entity invariants, not
  cross-cutting side effects: nh3 sanitize + slug/publish stamping in `Model.save()`, and the
  revision snapshot signal — all co-located with the write because they are part of *being a
  valid record*, not notifications (see §1.3, "Signal extraction … rejected").
