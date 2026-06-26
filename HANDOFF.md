# cmstack-django — HANDOFF

_Last refresh: 2026-06-26 (original REFACTOR_PLAN scope — F1–F15, UI U1–U7, README,
adversarial + completeness-critic — is COMPLETE, **and** the stricter Task-4 (E2E) criteria
the user added in the updated master prompt (`../prompts/cmstack-django.md`) are now ALSO
COMPLETE — see "DONE this session". No open required items remain; optional follow-ups are
listed at the bottom.). Read with [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md),
[`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md), [`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md)._

## Current state (verified, not asserted — 2026-06-26)
- Branch `refactor/service-repository-layer`: **69 commits**, PUSHED to `origin` (tracking set;
  NOT on `main`). Latest: `d1031a2` (F12 stdio MCP transport), `6bb6e80` (F12 OAuth 2.1 + SSE),
  `ca89901` (F9 arbitrary-depth + drag-drop), `a4cbc4c` (per-category RSS + dead-testid cleanup).
  **ALL REFACTOR_PLAN §7 deferred scope is now CLOSED — nothing deferred remains.**
- Full unit/integration suite: **466 passed, 10 deselected** (`.venv/bin/python -m pytest -q`).
- E2E: **10 passed** — `.venv/bin/python -m pytest tests/e2e -m e2e --ds=config.settings.test_e2e`
  (needs `playwright install chromium` + `cd frontend && npm run build` first).
- Lint/types clean: `.venv/bin/ruff check apps config` · `.venv/bin/python -m black --check apps
  config tests plugins` · `.venv/bin/python -m mypy apps config` → **Success, 0 issues**.
  NOTE: the venv's `black`/`mypy` console scripts have a stale shebang (venv created under the
  old `DjangoPress` path) — invoke via `.venv/bin/python -m black` / `-m mypy`, not the bare
  scripts. `ruff` is a native binary so `.venv/bin/ruff` works directly.
- Coverage: **~97%** overall (`pytest --cov=apps`). pytest-cov + factory_boy wired.
- CI (F13): `.github/workflows/ci.yml` — lint(ruff+black+mypy) / pytest+cov SQLite(90% floor) /
  Postgres job (`config.settings.test_postgres`, exercises the FTS branch) / Vite build / e2e.
- Lighthouse (real headless Chrome, built + Postgres-backed server): **home 98/100/96/100,
  post 100/100/96/100** (perf/a11y/best-practices/seo) — every category ≥95.
- Run app: `docker compose up` (or venv + `manage.py runserver`). Use `.venv/bin/python`
  directly — `source .venv/bin/activate` does NOT expose django in this shell.

## DONE this session — the updated-prompt Task-4 gaps (all closed; commit `5b3831d`)
All four items from the previous "REMAINING vs the updated prompt" are complete, TDD'd, and
independently completeness-critic-verified (verdict: all 4 criteria genuinely met, no
CRITICAL/MAJOR; only 2 harmless NITs — see end):
1. **E2E selectors are now `data-testid`.** Stable `data-testid` hooks added to the touched
   surfaces (home recent-post link, post-detail title/body, search result, dashboard post
   row/title/trash, post-form title/excerpt/status/Trix-editor/save, dark toggle, confirm
   dialog accept/cancel, media file/title/submit/asset) and the Playwright journeys switched
   to them. Form-field testids thread through `_field.html` via an OPTIONAL `testid` arg on the
   `aria_field` filter (`apps/dashboard/templatetags/dashboard_a11y.py`); media file/title via
   widget attrs in `apps/media/forms.py`. A11y landmark/heading/hreflang/JSON-LD assertions are
   DELIBERATELY kept role/attribute-based (converting them would defeat what they verify) —
   documented in the test-module docstring.
2. **Both missing canonical flows added** (`tests/e2e/test_journeys.py`): `test_author_creates_
   and_publishes_a_post` (real Trix authoring → publish → asserts public visibility of the
   round-tripped body) and `test_admin_uploads_media` (in-memory PNG → library). 8 → **10 e2e**.
   Shared `login()` helper + `png_upload` fixture added to `tests/e2e/conftest.py`.
   GOTCHA: media upload/library live at `/library/upload/` + `/library/` (NOT `/media/…`).
3. **REFACTOR_PLAN.md §8 + §9 added:** §8 per-layer test-status table (11 layers, none at zero,
   with representative test files); §9 per-event sync/async classification (`comment_created`
   and `contact_received` emails — both fire-and-forget via signal→observer, non-atomic,
   failure-isolated by `send_robust`/`fail_silently`, no broker; drop-in upgrade path to a real
   worker noted).
4. **(Optional) no-N+1 guard done:** `apps/content/tests/test_views.py::test_post_list_has_no_n_
   plus_one` warms the cached singletons then asserts the blog index issues the SAME query count
   for 2 vs 6 posts (locks in parler-translation + author prefetch).
- **Also wired the previously dead `factory_boy` dep:** `tests/factories.py`
  (`UserFactory`/`PostFactory`) + `tests/test_factories.py` smoke tests; consumed by the N+1
  guard. The "factories" layer was the only one genuinely at zero before.

### Open items remaining: NONE. ALL REFACTOR_PLAN §7 deferred scope is now CLOSED:
- **F9 menus — full scope delivered:** per-locale parler labels (`f1c0877`), arbitrary-depth
  recursive dropdown menus with cycle-protection + no-N+1 tree (`ca89901`), and drag-drop reorder
  (SortableJS progressive enhancement, keyboard ↑/↓ no-JS fallback, `ca89901`).
- **F12 API/MCP — full scope delivered:** OAuth 2.1 auth floor (django-oauth-toolkit, PKCE,
  read/write scopes) added ALONGSIDE token/session (`6bb6e80`); adversarially security-reviewed —
  no authz bypass; MCP write-scope enforced per-tool (incl. the empty-scope edge case). **Three
  MCP transports** over one registry + authz: JSON `POST /api/mcp/`, SSE `GET /api/mcp/sse`
  (`6bb6e80`), and **stdio** `manage.py mcp_stdio` (line-delimited JSON-RPC 2.0, `d1031a2`).
- **Other:** per-category RSS feeds + removal of the 3 dead container testids (`a4cbc4c`);
  blog-list `translations` prefetch (`28bd7ef`).
- Possible future (only if asked): integration — push to `main` / open a PR.

## Last session's deliverables (F13/F14/F15 + U5/U6/U7 + README + critic)
- **F13 CI**, **F15 mypy** (0 errors, django-stubs plugin + file-level `disable-error-code` on
  `apps/content/models.py` for parler's un-stubbed dynamics), **F14 E2E** (8 Playwright journeys).
- **U5**: accessible confirm dialog (replaced 11 `confirm()`), toasts, table bulk-select +
  `PostBulkActionView`→`bulk_trash_posts`→`PostRepository.editable_among`, empty-state, Trix aria.
  **U6**: form-field `aria-invalid`/`aria-describedby` via `dashboard_a11y.aria_field` →
  `_field.html`; locale tabs `role=tab`/`aria-selected`/`aria-current`. **U7**: hash-free woff2 +
  `<link rel=preload>` for the 2 critical latin fonts; WCAG-AA contrast fixes (darkened
  `--text-subtle`, migrated low-opacity ink → semantic tokens).
- **Task 5 README** rewritten (architecture/layering + 5 patterns, testing incl. e2e/lighthouse,
  CI, i18n, deployment; aligned with sibling-stack READMEs).
- **Completeness-critic** (independent subagent) found 1 CRITICAL: bulk-trash 500'd on
  non-integer `ids` → FIXED (`bulk_trash_posts` drops non-numeric ids) + regression test.
- GOTCHA learned: Django `{# #}` comments are SINGLE-LINE — a multi-line one containing a
  `{% include %}` silently self-includes (infinite recursion). Use `{% comment %}…{% endcomment %}`.

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

## DONE — full original plan (all ☑; see git log on the branch)
- **Task 2 architecture refactor** (above) — independently adversarially verified; greps confirm
  zero ORM in `apps/*/views.py` and no raw `Model.objects`/`get_object_or_404` in `apps/*/services.py`.
- **Task 1 feature parity:** F1 search-services, F2 coverage tooling, F3 RSS, F4 contact form
  (signal→observer), F5 comment-notification email (signal→observer), F6 soft-delete/trash/restore +
  likes, F7 revision-restore UI, F8 scheduled publishing, F9 menu builder, F10 author pages +
  profile, F11 media picker + swappable storage, F12 REST API + MCP, **F13 CI**, **F14 E2E**,
  **F15 mypy django-stubs (0 errors)**.
- **Task 3 UI (U1–U7):** semantic tokens + `.dark`, fonts, public shell, admin shell + dark
  toggle, U5 components (confirm dialog/toasts/bulk-select/empty-state/Trix aria), U6 a11y
  (form-field aria + locale-tab roles), U7 fonts preload + WCAG-AA contrast + **Lighthouse ≥95
  measured**.
- **Task 5 README** rewritten. **Completeness-critic** pass done (1 CRITICAL found+fixed).
- The actionable open items are in **"REMAINING vs the updated prompt"** near the top — start there.

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
> You are a senior Django engineer continuing the autonomous `cmstack-django` work under the
> updated master prompt `../prompts/cmstack-django.md` (read it — operating rules, model
> routing, the two hard architecture rules, and the Task-4 E2E requirements all live there).
>
> **First, orient — before any work:**
> 1. `cd cmstack-django`; you are already on the branch `refactor/service-repository-layer`
>    (69 commits, PUSHED to `origin`, NOT on `main`). Commit there; push as needed.
> 2. Read `HANDOFF.md` and `REFACTOR_PLAN.md` in full, then `../FEATURE_MATRIX.md` and
>    `../DESIGN_SYSTEM.md` (read-only canon — never edit the two shared specs).
> 3. Confirm the baseline yourself: `.venv/bin/python -m pytest -q` (expect **466 passed, 10
>    deselected**), `.venv/bin/ruff check apps config`, `.venv/bin/python -m mypy apps config`
>    (Success, 0 issues), and E2E `.venv/bin/python -m pytest tests/e2e -m e2e
>    --ds=config.settings.test_e2e` (needs `playwright install chromium` +
>    `cd frontend && npm run build`). Use `.venv/bin/python -m black`/`-m mypy` (the bare
>    console scripts have a stale shebang). Expect **10 e2e passed**.
>
> **Operating rules (unchanged):** work autonomously inside `cmstack-django/`; respond to me in
> **Russian**, keep all code/comments/commits/docs in **English**; Superpowers framework
> (writing-plans / TDD / subagent-driven-development / requesting-code-review /
> verification-before-completion); orchestrate via parallel subagents and adversarial
> verification per the master prompt. **Commit messages must NOT contain any `Co-Authored-By`
> trailer.**
>
> **Two NON-NEGOTIABLE architecture rules (already in force — preserve in every new file):**
> (1) `apps/*/views.py` hold ZERO business logic and ZERO ORM (HTTP boundary only);
> (2) `apps/*/services.py` NEVER touch the ORM — data access via `apps/<app>/repositories.py`;
> side effects via Django signals → receivers. Layering: view → service → repository → manager
> → model, plus service → signal → receiver.
>
> **DONE (do NOT redo):** the whole original REFACTOR_PLAN — architecture refactor (all apps,
> adversarially verified), feature parity **F1–F15**, UI **U1–U7** (Lighthouse ≥95 measured),
> README rewrite, two completeness-critic passes — **AND** the updated prompt's stricter Task-4
> (E2E) criteria: `data-testid` selectors, the content-create→publish + media-upload journeys,
> the REFACTOR_PLAN §8 per-layer test-status table + §9 sync/async classification, a no-N+1
> guard, and `factory_boy` wired — **AND ALL of REFACTOR_PLAN §7's deferred scope**: full F9
> menus (per-locale parler labels + arbitrary-depth recursive dropdowns + drag-drop reorder) and
> full F12 (OAuth 2.1 auth floor via django-oauth-toolkit + all three MCP transports — JSON, SSE,
> and stdio — security-reviewed, no authz bypass). 466 unit + 10 e2e pass; ruff/black/mypy +
> `manage.py check` clean.
>
> **No work remains; §7 is fully closed (nothing deferred).** If asked for more, the only step
> left is integration — push to `main` / open a PR (branch is pushed to `origin`). Confirm scope
> with me before starting — the autonomous brief is complete.
