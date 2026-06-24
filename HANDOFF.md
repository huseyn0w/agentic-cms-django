# cmstack-django — HANDOFF

_Last refresh: 2026-06-24. Read with [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md),
[`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md), [`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md)._

## Current state (verified, not asserted)
- Full test suite: **250 passed** (`.venv/bin/python -m pytest -q`). Was 218 at start.
- Lint: `.venv/bin/ruff check apps` → clean.
- Coverage: **95%** overall (`pytest --cov=apps`). pytest-cov + factory_boy installed and
  wired (`pyproject.toml [tool.coverage.*]`, `requirements/dev.txt`).
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
   - ☐ **RESUME HERE → U4 admin shell + dark-mode toggle.** Tokens + `.dark` are ready; the
     toggle is an ADMIN feature (DESIGN_SYSTEM §2/§5 topbar). Work: migrate the ~15
     `apps/dashboard/templates/*` + `dashboard/base.html` off hardcoded `bg-white`/status
     colours (`bg-green-100` in post_list/plugins) to tokens (`bg-surface`/`surface-2`,
     semantic `success/warning/error` badges); sidebar active = `surface-2` + 2px `primary`
     left bar + mono group labels; topbar: add dark/light toggle (Alpine + localStorage + a
     no-FOUC inline `<script>` in dashboard base that sets `.dark` on <html> before paint) +
     avatar dropdown; messages → semantic Alert banners. Also `admin.css` `.dp-form` + Trix
     chrome. Then U5 components, U6 a11y, U7 perf/Lighthouse. **U4 admin shell** (sidebar
     style, topbar **dark/light toggle** wiring `darkMode:"class"` + localStorage, avatar
     dropdown, semantic alerts), **U5 components** (breadcrumbs, dropdown, avatar, dropzone,
     sortable, modals, toasts, table bulk-select, empty states, badges, rich-text toolbar),
     **U6 a11y** (ARIA pass, focus rings via `--ring`, tabs roles, pagination nav), **U7 perf**
     (font `<link rel=preload>` 2 weights + subset, Lighthouse ≥95 measured, responsive images).
   - Migrate template utilities from `paper/ink/accent` → semantic `bg/surface/text/text-muted/
     primary/border` as you touch each surface, then drop the aliases.
   - Build after frontend edits: `cd frontend && npm run build` (or docker `--renew-anon-volumes`).
4. **Task 1 — feature parity (REFACTOR_PLAN §2).** Build through the new layers (view→service→
   repository; effects→signal). Suggested order: F5 comment email (also demos observer), F3
   RSS, F4 contact, F6 soft-delete+likes, F7 revision-restore UI, F8 scheduled publish, F9
   menus, F10 authors/profile, F11 media picker+storage driver, F12 REST API + MCP (largest),
   F13 CI, F14 E2E, F15 mypy django plugin.
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
> You are a senior Django engineer continuing the autonomous `cmstack-django` refactor. Read
> `cmstack-django/HANDOFF.md`, `cmstack-django/REFACTOR_PLAN.md`, `../FEATURE_MATRIX.md` and
> `../DESIGN_SYSTEM.md` first (specs are read-only canon — do not edit them). Operating rules:
> work autonomously inside `cmstack-django/` (no permission for read/edit/test/manage.py/git);
> respond to me in **Russian**, keep all code/comments/docs in English; use the Superpowers
> framework (writing-plans / TDD / subagent-driven-development / requesting-code-review /
> verification-before-completion) and follow rigid skills exactly. Two NON-NEGOTIABLE
> architecture rules are already in force and MUST be preserved: (1) views hold zero business
> logic and zero ORM (HTTP boundary only); (2) services never touch the ORM directly — only via
> the `repositories.py` layer — and side effects go through Django signals/observers. Layering:
> view → service → repository → manager → model. The architecture refactor is DONE and verified
> (250 tests pass, ruff clean, 95% coverage, zero ORM in views/services per grep). **Resume from
> the first PENDING item in HANDOFF.md**: (1) adversarial verification of the refactor (retry
> subagents — they were 529-throttled), then (2) close the two coverage gaps, then (3) Task 3 UI
> convergence starting with U1 tokens + U2 fonts. Use `.venv/bin/python -m pytest` (not `source
> activate`). Show real test/coverage output; never claim passing without the run.
