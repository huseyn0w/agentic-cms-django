"""End-to-end user journeys driven through a real headless browser.

Covers the four journey families called out in the refactor plan (F14):
auth, content, SEO, and i18n/theme. Each test runs against a live Django server
(`live_server`) serving the built frontend bundle, so JS-dependent behaviour
(Alpine dark-mode toggle, language switch) is exercised for real.
"""

from __future__ import annotations

import re

from playwright.sync_api import expect


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
    expect(page.get_by_text("Hello E2E World").first).to_be_visible()


def test_reader_opens_a_published_post(live_server, page, published_post):
    page.goto(live_server.url)
    page.get_by_role("link", name="Hello E2E World").first.click()

    expect(page).to_have_url(re.compile(re.escape(published_post.slug)))
    expect(page.get_by_role("heading", name="Hello E2E World")).to_be_visible()
    expect(
        page.get_by_text("A complete journey through the published article body.")
    ).to_be_visible()
    # Breadcrumb landmark from the shared partial.
    expect(page.get_by_role("navigation", name="Breadcrumb")).to_be_visible()


def test_search_returns_the_post(live_server, page, published_post):
    page.goto(f"{live_server.url}/search/?q=Hello")
    expect(page.get_by_text("Hello E2E World").first).to_be_visible()


# --------------------------------------------------------------------------- #
# SEO journey
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
# i18n journey
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
    # Sign in through the real allauth form.
    page.goto(f"{live_server.url}/accounts/login/")
    page.locator("input[name='login']").fill("boss")
    page.locator("input[name='password']").fill("pw-secret-123")
    page.locator("button[type='submit']").first.click()

    # The admin panel is now reachable.
    page.goto(f"{live_server.url}/dashboard/")
    expect(page).to_have_url(re.compile(r"/dashboard/"))

    html = page.locator("html")
    expect(html).not_to_have_class(re.compile(r"\bdark\b"))

    # Flip to dark mode via the Alpine topbar toggle.
    page.get_by_role("button", name="Switch to dark mode").click()
    expect(html).to_have_class(re.compile(r"\bdark\b"))

    # The choice is persisted in localStorage and survives a reload (no-FOUC script).
    page.reload()
    expect(page.locator("html")).to_have_class(re.compile(r"\bdark\b"))


def test_admin_confirm_dialog_trashes_a_post(live_server, page, admin_user, published_post):
    page.goto(f"{live_server.url}/accounts/login/")
    page.locator("input[name='login']").fill("boss")
    page.locator("input[name='password']").fill("pw-secret-123")
    page.locator("button[type='submit']").first.click()

    page.goto(f"{live_server.url}/dashboard/posts/")
    expect(page.get_by_text("Hello E2E World")).to_be_visible()

    # Clicking a destructive action opens the accessible dialog instead of submitting.
    page.get_by_role("button", name="Trash").first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()

    # Confirming submits the form; the post is soft-deleted and leaves the live list.
    page.get_by_role("button", name="Confirm").click()
    expect(page.get_by_text("Hello E2E World")).to_have_count(0)
