# cmstack-django — HANDOFF

_Last refresh: 2026-06-26 (original REFACTOR_PLAN scope — F1–F15, UI U1–U7, README,
adversarial + completeness-critic — is COMPLETE. The user then updated the master prompt
(`../prompts/cmstack-django.md`); a few of its STRICTER acceptance criteria are not yet
met — see "REMAINING vs the updated prompt". Resume there.). Read with
[`REFACTOR_PLAN.md`](REFACTOR_PLAN.md), [`../FEATURE_MATRIX.md`](../FEATURE_MATRIX.md),
[`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md)._

## Current state (verified, not asserted — 2026-06-26)
- Branch `refactor/service-repository-layer`: **37 commits**, LOCAL only (NOT pushed, NOT on `main`).
- Full unit/integration suite: **388 passed, 8 deselected** (`.venv/bin/python -m pytest -q`).
- E2E: **8 passed** — `.venv/bin/python -m pytest tests/e2e -m e2e --ds=config.settings.test_e2e`
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

## REMAINING vs the updated prompt (`../prompts/cmstack-django.md`) — RESUME HERE
The updated prompt strengthened Task 4 (E2E) beyond what was built. Open items, ordered:
1. **E2E selectors must be `data-testid`** (prompt §4 + self-check). Today the journeys use
   `get_by_role`/`get_by_text`; there are ZERO `data-testid` in templates. Add stable
   `data-testid` attributes to the touched surfaces and switch the E2E selectors to them.
2. **E2E canonical-flow gaps** (prompt §4: "login/auth, content create → publish, media upload,
   search, main dashboard actions"). Covered today: home, reader, search, SEO, login-gate,
   lang-switch, dark-toggle, confirm-dialog-trash. MISSING: **content create → publish** (a
   dashboard authoring flow) and **media upload**. Add both (admin user has the perms).
3. **REFACTOR_PLAN docs the prompt now requires:** (a) a **per-layer test-status list**
   (models/managers, views, forms/serializers, permissions, repositories, services,
   signals/receivers, templates, template tags, management commands, factories — none at zero);
   (b) a **per-event sync-vs-async classification** for the signal/observer effects
   (`comment_created` email, `contact_*` email — both async/fire-and-forget; none are atomic).
4. (Optional, prompt §test) consider `assertNumQueries` guards on the hottest list views to lock
   in "no N+1" as an explicit regression, if not already implicit.

Everything else in the prompt's self-check is satisfied (see the DONE sections below).

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
> 1. `cd cmstack-django`; you are already on the LOCAL branch `refactor/service-repository-layer`
>    (37 commits, NOT pushed, NOT on `main`). Commit there; push only if asked.
> 2. Read `HANDOFF.md` and `REFACTOR_PLAN.md` in full, then `../FEATURE_MATRIX.md` and
>    `../DESIGN_SYSTEM.md` (read-only canon — never edit the two shared specs).
> 3. Confirm the baseline yourself: `.venv/bin/python -m pytest -q` (expect **388 passed, 8
>    deselected**), `.venv/bin/ruff check apps config`, `.venv/bin/python -m mypy apps config`
>    (Success, 0 issues), and E2E `.venv/bin/python -m pytest tests/e2e -m e2e
>    --ds=config.settings.test_e2e` (needs `playwright install chromium` +
>    `cd frontend && npm run build`). Use `.venv/bin/python -m black`/`-m mypy` (the bare
>    console scripts have a stale shebang). Expect **8 e2e passed**.
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
> README rewrite, and a completeness-critic pass. 388 unit + 8 e2e pass; ruff/black/mypy clean.
>
> **RESUME HERE — close the gaps the UPDATED prompt added (see HANDOFF "REMAINING vs the
> updated prompt"), TDD + show real output:**
> 1. Add stable **`data-testid`** attributes to the relevant templates and switch the Playwright
>    selectors to them (the prompt requires `data-testid`, not role/text).
> 2. Add the missing **canonical E2E flows: content create → publish** (dashboard authoring) and
>    **media upload** — keep parity with the sibling stacks' flow list.
> 3. Record in `REFACTOR_PLAN.md`: the **per-layer test-status list** and the **per-event
>    sync/async classification** for the signal effects (both current effects are async email).
> 4. Then re-run the completeness-critic and refresh `HANDOFF.md`.
