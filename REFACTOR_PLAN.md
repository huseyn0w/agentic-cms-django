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
  — introduced there via Django's `STORAGES` setting, not a bespoke class hierarchy. ◐
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
| F6 | **Soft-delete/trash/restore** (posts+pages) + **post likes** | absent | M | copy ts: `deleted_at`, manager scoping, trash/restore views; `Like` model + endpoint. |
| F7 | **Revision restore UI** (storage exists, restore absent) | partial | M | dashboard diff+restore view; net-new for all 3. |
| F8 | **Scheduled publishing** (`scheduled_at` + worker) | absent | M | management command/cron auto-publishes due content. |
| F9 | **Menu builder** + public menu rendering | absent | M | copy laravel; sortable list (keyboard-accessible). |
| F10 | **Author public pages** + **self-service profile edit** | absent (fields exist) | M | `/authors/<id>`, `/account`; ProfilePage JSON-LD; avatar upload. |
| F11 | **Media picker in editor** + **swappable storage driver** | absent | M | picker modal into editor; storage via Django `STORAGES` (Strategy). |
| F12 | **Public REST API** + **MCP server** | absent | L | DRF read API + gated write; MCP port ts tool list, OAuth-floor (laravel model). Largest item. |
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

## 7. Matrix-gap flags for the user
None so far — the matrix's "cmstack-django needs" list matched the code exactly. Record any
discovered discrepancy here (do not edit `../FEATURE_MATRIX.md`).
