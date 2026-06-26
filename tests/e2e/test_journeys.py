"""End-to-end user journeys driven through a real headless browser.

Covers the canonical journey families called out in the master prompt (Task 4):
login/auth, content create → publish, media upload, search, SEO, i18n/theme, and
the main dashboard actions. Each test runs against a live Django server
(`live_server`) serving the built frontend bundle, so JS-dependent behaviour
(Alpine dark-mode toggle, the Trix editor, the confirm dialog, the language
switch) is exercised for real.

Element/control selectors use stable ``data-testid`` hooks (master prompt §4) so
the journeys survive copy and styling churn. Assertions whose *purpose* is to
verify accessibility semantics (landmark roles, heading levels, hreflang, the
skip link) deliberately stay role/attribute based — converting those to
data-testid would defeat what they check.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect

from .conftest import login


# --------------------------------------------------------------------------- #
# Content journeys
# --------------------------------------------------------------------------- #
def test_home_shows_landmarks_and_recent_post(live_server, page, published_post):
    page.goto(live_server.url)

    # Accessible shell: a skip link, a nav landmark, and a single top heading.
    expect(page.get_by_role("link", name="Skip to content")).to_be_attached()
    expect(page.get_by_role("navigation").first).to_be_visible()
    expect(page.get_by_role("heading", level=1).first).to_be_visible()

    # The CMS renders its own recent published posts on the landing page.
    expect(page.get_by_test_id("recent-post-link").first).to_have_text("Hello E2E World")


def test_reader_opens_a_published_post(live_server, page, published_post):
    page.goto(live_server.url)
    page.get_by_test_id("recent-post-link").first.click()

    expect(page).to_have_url(re.compile(re.escape(published_post.slug)))
    expect(page.get_by_test_id("post-title")).to_have_text("Hello E2E World")
    expect(page.get_by_test_id("post-body")).to_contain_text(
        "A complete journey through the published article body."
    )
    # Breadcrumb landmark from the shared partial (a11y semantics, kept role-based).
    expect(page.get_by_role("navigation", name="Breadcrumb")).to_be_visible()


def test_search_returns_the_post(live_server, page, published_post):
    page.goto(f"{live_server.url}/search/?q=Hello")
    results = page.get_by_test_id("search-result")
    expect(results.first).to_contain_text("Hello E2E World")


# --------------------------------------------------------------------------- #
# Authoring journey: create → publish → visible to the public (JS Trix editor)
# --------------------------------------------------------------------------- #
def test_author_creates_and_publishes_a_post(live_server, page, admin_user):
    login(page, live_server, "boss", "pw-secret-123")

    page.goto(f"{live_server.url}/dashboard/posts/new/")
    page.get_by_test_id("post-title").fill("Published Through The Editor")
    page.get_by_test_id("post-excerpt").fill("A post authored end-to-end.")

    # Write the body through the real Trix editor (syncs to the hidden input).
    editor = page.get_by_test_id("post-body-editor")
    editor.click()
    page.keyboard.type("Body written through the Trix editor in a browser.")

    # Publish, not draft.
    page.get_by_test_id("post-status").select_option("published")
    page.get_by_test_id("post-save").click()

    # Lands back on the post list with the new row present.
    expect(page).to_have_url(re.compile(r"/dashboard/posts/"))
    expect(
        page.get_by_test_id("post-row-title").filter(has_text="Published Through The Editor")
    ).to_be_visible()

    # The published post is now live for the public: reach it from the landing page.
    page.goto(live_server.url)
    page.get_by_test_id("recent-post-link").filter(
        has_text="Published Through The Editor"
    ).first.click()
    expect(page.get_by_test_id("post-title")).to_have_text("Published Through The Editor")
    expect(page.get_by_test_id("post-body")).to_contain_text("Body written through the Trix editor")


# --------------------------------------------------------------------------- #
# Media upload journey
# --------------------------------------------------------------------------- #
def test_admin_uploads_media(live_server, page, admin_user, png_upload):
    login(page, live_server, "boss", "pw-secret-123")

    page.goto(f"{live_server.url}/library/upload/")
    page.get_by_test_id("media-file").set_input_files(files=png_upload)
    page.get_by_test_id("media-title").fill("E2E uploaded asset")
    page.get_by_test_id("media-upload-submit").click()

    # Redirects to the library where the new asset is listed.
    expect(page).to_have_url(re.compile(r"/library/"))
    expect(page.get_by_test_id("media-asset").filter(has_text="E2E uploaded asset")).to_be_visible()


# --------------------------------------------------------------------------- #
# SEO journey (meta/JSON-LD locators are inherently attribute-based)
# --------------------------------------------------------------------------- #
def test_post_emits_jsonld_and_open_graph(live_server, page, published_post):
    page.goto(f"{live_server.url}{published_post.get_absolute_url()}")

    ld = page.locator('script[type="application/ld+json"]')
    expect(ld.first).to_be_attached()
    joined = " ".join(ld.all_text_contents())
    assert "BreadcrumbList" in joined
    assert "Article" in joined

    og_title = page.locator('meta[property="og:title"]')
    expect(og_title).to_have_count(1)
    assert og_title.get_attribute("content")
    assert page.locator('link[rel="canonical"]').get_attribute("href")


# --------------------------------------------------------------------------- #
# i18n journey (hreflang is the semantic surface under test)
# --------------------------------------------------------------------------- #
def test_language_switch_to_german(live_server, page, published_post):
    page.goto(live_server.url)
    page.locator("a[hreflang='de']").first.click()

    expect(page).to_have_url(re.compile(r"/de(/|$)"))
    expect(page.locator("html")).to_have_attribute("lang", "de")


# --------------------------------------------------------------------------- #
# Auth + theme journey (JS-dependent)
# --------------------------------------------------------------------------- #
def test_dashboard_requires_login(live_server, page):
    page.goto(f"{live_server.url}/dashboard/")
    expect(page).to_have_url(re.compile(r"/accounts/login/"))
    expect(page.locator("input[name='password']")).to_be_visible()


def test_login_then_dark_mode_toggle_persists(live_server, page, admin_user):
    login(page, live_server, "boss", "pw-secret-123")

    # The admin panel is now reachable.
    page.goto(f"{live_server.url}/dashboard/")
    expect(page).to_have_url(re.compile(r"/dashboard/"))

    html = page.locator("html")
    expect(html).not_to_have_class(re.compile(r"\bdark\b"))

    # Flip to dark mode via the Alpine topbar toggle.
    page.get_by_test_id("dark-toggle").click()
    expect(html).to_have_class(re.compile(r"\bdark\b"))

    # The choice is persisted in localStorage and survives a reload (no-FOUC script).
    page.reload()
    expect(page.locator("html")).to_have_class(re.compile(r"\bdark\b"))


def test_admin_confirm_dialog_trashes_a_post(live_server, page, admin_user, published_post):
    login(page, live_server, "boss", "pw-secret-123")

    page.goto(f"{live_server.url}/dashboard/posts/")
    expect(page.get_by_test_id("post-row-title")).to_have_text("Hello E2E World")

    # Clicking a destructive action opens the accessible dialog instead of submitting.
    page.get_by_test_id("post-trash").first.click()
    dialog = page.get_by_test_id("confirm-dialog")
    expect(dialog).to_be_visible()

    # Confirming submits the form; the post is soft-deleted and leaves the live list.
    page.get_by_test_id("confirm-accept").click()
    expect(page.get_by_test_id("post-row-title")).to_have_count(0)
