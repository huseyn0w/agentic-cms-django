# cmstack-django — HANDOFF

_Last refresh: 2026-06-24. Read with [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md),
[`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md), [`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md)._

## Current state (verified, not asserted)
- Full test suite: **305 passed** (`.venv/bin/python -m pytest -q`). Was 218 at start.
- Lint: `.venv/bin/ruff check apps config` → clean.
- Coverage: **~96%** overall (content/dashboard ≥93% each; `pytest --cov=apps`). pytest-cov +
  factory_boy installed and wired (`pyproject.toml [tool.coverage.*]`, `requirements/dev.txt`).
- Run app: `docker compose up` (or venv + `manage.py runserver`). Tests: `.venv/bin/python -m
  pytest`. Use `.venv/bin/python` directly — `source .venv/bin/activate` did not expose django
  in this shell, but `.venv/bin/python` works.

## DONE — Architecture (Task 2), per the two hard rules the user added mid-session
Two non-negotiable rules now govern (see REFACTOR_PLAN §0 + §0a):
1. **Views = HTTP boundary only.** Zero business logic, zero ORM in any `apps/*/views.py`.
2. **Services never touch the ORM** — only via a **repository** layer; side effects via signals.

Layering enforced everywhere: `view → service → repository → manager/QuerySet → model`.
- New `services.py` in: content, comments, core, media, seo, dashboard (+ existing search).
- New `repositories.py` in: content, comments, core, media, seo, search, accounts.
- Logic extractions (all tested): `Post.objects.editable_by(user)` (QuerySet),
  `Post.gate_publish_state(user)`, `Comment.approve()/mark_spam()` (model methods — entity
  behavior, intentionally kept), `comments.services.submit_comment` (returns an outcome enum:
  CREATED/INVALID/DISABLED/LOGIN_REQUIRED — owns ALL comment gating so the view only maps
  outcome→HTTP), `comments.services.moderate`, `dashboard.services.dashboard_stats`.
- Verification greps (both empty): ORM in `apps/*/views.py`; raw `Model.objects`/
  `get_object_or_404` in `apps/*/services.py`.
- Also done: **F1** search now includes Services; **F2** coverage tooling.

## Decisions / rejected (so they're not relitigated)
- `model = X` on Create/Update/Delete generic views is KEPT — it's declarative config, not an
  ORM call; the grep treats it as clean. List views' `queryset=`/`get_queryset` ORM was moved
  to services.
- Model methods (`approve`/`mark_spam`/`gate_publish_state`/`save()` invariants) are legit
  entity behavior, NOT "raw ORM in a service" — services call them. Repositories own queries +
  create-from-form + delete + counts.
- Services currently fire NO inline side effects (sanitize/cache/revisions already live in
  `model.save()` / existing signals), so the observer half of rule 2 is satisfied today. The
  signal→receiver pattern is to be introduced with the FIRST real effect = **F5 comment-
  notification email** (build: `submit_comment` emits a `comment_created` Django signal; a
  receiver in `apps/comments/signals.py` sends mail; test with locmem backend).

## PENDING (ordered) — resume here
1. ☑ **Adversarial verification — DONE.** 2 independent skeptics (behavior+security;
   N+1+parler+layering) could not break behavior/security/N+1/translations. One minor finding
   (services calling `SiteSettings.load()` directly) FIXED in commit ea4ff6a and re-verified.
2. ◐ **Coverage gaps:** `content/services.py` now 92% (visibility tests added). STILL OPEN:
   `apps/search/repositories.py` 70% — Postgres FTS branch is SQLite-untestable; needs a
   Postgres CI job (see §F13/F14).
3. **Task 3 — UI convergence (largest remaining).** See REFACTOR_PLAN §3.
   - ☑ U1 tokens DONE: full §2 semantic set + `.dark` in `frontend/src/styles.css`, bridged in
     `tailwind.config.js` (`darkMode:"class"`); legacy `paper/ink/accent` aliased; midnight
     theme palette updated to new tokens; radius tokens added.
   - ☑ U2 fonts DONE: Newsreader + Inter + Geist Mono (package.json/main.js/tailwind/.dp-prose).
     `cd frontend && npm run build` verified (main.css 6.7KB gz, main.js 16.7KB gz).
   - ☑ U3 public side DONE: sticky 64px header + scroll-shadow + blur, focus-trapped mobile
     drawer (@alpinejs/focus `x-trap`), skip link + `#content`, header/footer/base on semantic
     tokens, button primitives rebuilt (md radius + 5 variants + focus ring), and CSS
     primitives (.dp-auth/.dp-form/.dp-prose) + public cards (post_detail/_comment/allauth)
     migrated off hardcoded `bg-white` → `bg-surface` so they adapt to themes / are dark-ready.
     Guard test: `test_home_has_a11y_shell_landmarks`. (Public list/detail templates still use
     `ink/accent/paper` aliases — they render correctly via the alias bridge; pure cosmetic
     rename to semantic names is optional, deferrable.)
   - ☑ U4 admin shell + dark mode DONE: `dashboard/base.html` sidebar(260px)/topbar(56px) on
     tokens; no-FOUC inline script sets `.dark` from `localStorage('admin-theme')`/system pref;
     topbar dark/light toggle (Alpine+localStorage, sun/moon) + avatar dropdown + `#content`;
     `_navlink` active = surface-2 + 2px primary bar + aria-current; ALL dashboard/media
     templates off `bg-white`→`bg-surface`; status badges → `success-bg/success`/`surface-2`;
     `admin.css` `.dp-form`+Trix on tokens. Guard: `test_dashboard_shell_has_dark_toggle_and_landmarks`.
     Zero hardcoded `bg-white`/palette colours remain anywhere (grep CLEAN).
   - ◐ U5/U6 STARTED: reusable `_breadcrumbs.html` (on post/service/page detail, mirrors
     BreadcrumbList JSON-LD) + accessible pagination (`nav[aria-label=Pagination]` + aria-current
     + tokens) across admin lists + public post_list + search. Guard tests added.
   - ☐ **RESUME HERE → finish U5 components** (modals/dialogs to replace `confirm()`, toasts for
     messages, table bulk-select + backend bulk actions, empty-state component, rich-text
     toolbar aria, dropdown already done via avatar menu), **U6 a11y** (audit remaining ARIA,
     locale tabs `role=tab`/`tabpanel`, form errors `aria-invalid`/`aria-describedby`), **U7
     perf** (font `<link rel=preload>` + subset, real Lighthouse ≥95 run — needs server+browser).
     **U4 admin shell** (sidebar
     style, topbar **dark/light toggle** wiring `darkMode:"class"` + localStorage, avatar
     dropdown, semantic alerts), **U5 components** (breadcrumbs, dropdown, avatar, dropzone,
     sortable, modals, toasts, table bulk-select, empty states, badges, rich-text toolbar),
     **U6 a11y** (ARIA pass, focus rings via `--ring`, tabs roles, pagination nav), **U7 perf**
     (font `<link rel=preload>` 2 weights + subset, Lighthouse ≥95 measured, responsive images).
   - Migrate template utilities from `paper/ink/accent` → semantic `bg/surface/text/text-muted/
     primary/border` as you touch each surface, then drop the aliases.
   - Build after frontend edits: `cd frontend && npm run build` (or docker `--renew-anon-volumes`).
4. **Task 1 — feature parity (REFACTOR_PLAN §2).** Build through the new layers (view→service→
   repository; effects→signal). ☑ F1 search-services, ☑ F2 coverage, ☑ **F5 comment-email
   (signal→observer)**, ☑ **F3 RSS**, ☑ **F4 contact form (signal→observer)**, ☑ **F6 soft-
   delete/trash/restore (posts+pages) + post likes** (`SoftDeleteModel` mixin +
   `SoftDeleteManager` hiding trash by default; dashboard delete→trash + trash list + restore +
   permanent-delete; `Like` toggle endpoint + a11y button; 21 tests), ☑ **F7 revision-restore
   UI** (`RevisionRepository` + shared `dashboard/revisions.html`: per-language history + difflib
   diff + restore via `Post/Page.restore_revision` model transition; owner-scoped, gated on
   change_post/change_page; 7 tests), ☑ **F8 scheduled publishing** (`SchedulableMixin` on
   Post/Page/Service + `due_for_publish()` + `publish_scheduled` cron command; datetime-local
   field in forms, post-list badge; 9 tests). REMAINING order:
   F9 menus, F10
   authors/profile, F11 media picker+storage driver, F12 REST API + MCP (largest), F13 CI,
   F14 E2E, F15 mypy django plugin.
5. **Task 5 — rewrite README** after the above; align with the other two stacks.
6. **Completeness-critic** Opus pass before declaring done (prompt §"production quality bar").

## Gotchas
- parler: query translated fields via `.language(code)`/`translations__field`, never
  `filter(title=...)`. Root `conftest.py` resets active language per test.
- Tests run on SQLite → only the search `icontains` fallback is exercised; the Postgres
  `SearchVector` path in `search/repositories.py` is untested without a Postgres CI job.
- Frontend changes need `docker compose up -d --build --renew-anon-volumes` (stale dist
  volume), or run Vite locally.
- Do NOT edit `../FEATURE_MATRIX.md` / `../DESIGN_SYSTEM.md` (parallel sessions depend on them).
  No matrix discrepancies found so far (REFACTOR_PLAN §7).

---

## Ready-to-paste continuation prompt (new window)
> You are a senior Django engineer continuing the autonomous `cmstack-django` refactor.
>
> **First, orient — do these before any work:**
> 1. `cd` to the project; run `git checkout refactor/service-repository-layer` (all prior work
>    lives on this LOCAL branch — 15 commits, NOT pushed, NOT on `main`).
> 2. Read `cmstack-django/HANDOFF.md` and `cmstack-django/REFACTOR_PLAN.md` in full, then
>    `../FEATURE_MATRIX.md` and `../DESIGN_SYSTEM.md` (read-only canon — never edit the two
>    shared specs).
> 3. Confirm the baseline yourself: `.venv/bin/python -m pytest -q` (expect **305 passed**) and
>    `.venv/bin/ruff check apps config`. Use `.venv/bin/python` directly — `source .venv/bin/activate`
>    does NOT expose Django in this shell. Frontend build: `cd frontend && npm run build`.
>
> **Operating rules (unchanged):** work autonomously inside `cmstack-django/` (no permission
> needed for read/edit/test/manage.py/git); respond to me in **Russian**, keep all code,
> comments, commit messages and docs in **English**; use the Superpowers framework
> (writing-plans / TDD / subagent-driven-development / requesting-code-review /
> verification-before-completion), follow rigid skills exactly. **Commit messages must NOT
> contain any `Co-Authored-By` trailer** (the user had it stripped from history — do not
> re-add it). Branch-first is already done; commit to `refactor/service-repository-layer`; only
> push if asked.
>
> **Two NON-NEGOTIABLE architecture rules, already in force — preserve them in every new file:**
> (1) views (`apps/*/views.py`) hold ZERO business logic and ZERO ORM — HTTP boundary only;
> (2) services (`apps/*/services.py`) NEVER touch the ORM — all data access via
> `apps/<app>/repositories.py`; side effects via Django signals → observers (see
> `apps/comments/signals.py`, `apps/core/signals.py` for the pattern). Layering:
> view → service → repository → manager → model, plus service → signal → receiver for effects.
>
> **DONE so far (don't redo):** the architecture refactor (all apps; independently
> adversarially verified; zero ORM in views/services per grep); feature parity F1 (search incl.
> services), F2 (coverage tooling), F3 (RSS /rss.xml), F4 (contact form), F5 (comment-notification
> email) — all via the signal/observer pattern with tests; UI U1 (semantic tokens + `.dark`),
> U2 (Newsreader/Inter/Geist Mono fonts), U3 (public shell: sticky header, focus-trap mobile
> drawer, skip link, buttons, public surfaces on tokens/dark-ready), U4 (admin shell + working
> dark-mode toggle, all dashboard templates tokenised), U5/U6 start (breadcrumbs partial +
> accessible pagination), **F6 soft-delete/trash/restore (posts+pages) + post likes**,
> **F7 revision-restore UI** (history + diff + restore for posts/pages), and **F8 scheduled
> publishing** (`scheduled_at` + `publish_scheduled` cron command).
> 305 tests pass, ruff clean, ~97% coverage, Vite build within budget.
>
> **RESUME HERE (ordered):** Task 1 feature parity — **F9 menu builder + public menu
> rendering**, then
> F10 author pages + self-service profile, F11 media picker + swappable storage driver, F12 REST
> API + MCP (largest), F13 CI, F14 E2E, F15 wire mypy `django-stubs` plugin. Also finish UI U5
> (modals replacing `confirm()`, toasts, table bulk-select + backend bulk actions, empty-state
> component, rich-text toolbar aria), U6 (remaining ARIA, locale tabs roles, form-error
> aria-invalid/describedby), U7 (font `<link rel=preload>` + subset, REAL Lighthouse ≥95 run —
> needs a running server + browser). Finally Task 5 (rewrite README) + a completeness-critic pass.
> Build each feature through the view→service→repository (+signal) layering; TDD; show real
> test/coverage output — never claim passing without the run. The remaining Postgres-FTS branch
> in `search/repositories.py` is only coverable via a Postgres CI job (F13).
