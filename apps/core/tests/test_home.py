import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.content.models import Post, Status

User = get_user_model()


@pytest.mark.django_db
def test_home_status_ok(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_home_uses_expected_template(client):
    response = client.get(reverse("core:home"))
    assert "core/home.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_home_renders_brand(client):
    response = client.get(reverse("core:home"))
    assert b"DjangoPress" in response.content


@pytest.mark.django_db
def test_home_showcases_recent_published_posts(client):
    """The landing demonstrates the CMS by rendering its own real content."""
    author = User.objects.create_user(username="writer")
    Post.objects.create(title="Shipping Editorial UX", author=author, status=Status.PUBLISHED)
    Post.objects.create(title="Unfinished Draft", author=author)  # draft
    html = client.get(reverse("core:home")).content
    assert b"Shipping Editorial UX" in html
    assert b"Unfinished Draft" not in html


@pytest.mark.django_db
def test_home_hero_ctas_are_real_links(client):
    """No dead '#' placeholder CTAs — the hero points at real destinations."""
    html = client.get(reverse("core:home")).content.decode()
    assert reverse("account_signup") in html
    assert reverse("content:post_list") in html
    assert 'href="#"' not in html


@pytest.mark.django_db
def test_home_drops_stale_phase_badge(client):
    """The placeholder 'Phase 1 · Foundation' badge must be gone."""
    assert b"Phase 1" not in client.get(reverse("core:home")).content


@pytest.mark.django_db
def test_home_emits_hreflang_alternates(client):
    """The landing has a /de/ variant, so it must still advertise hreflang
    alternates (regression guard: it extends base.html, not the content shell)."""
    html = client.get(reverse("core:home")).content
    assert b'rel="alternate"' in html
    assert b'hreflang="de"' in html
    assert b'hreflang="x-default"' in html


@pytest.mark.django_db
def test_home_applies_active_theme_palette(client):
    """The landing must honor the active theme (it extends base.html, not the
    content shell, so it has to pull in the palette include itself)."""
    from apps.themes import registry

    registry.activate_theme("midnight")
    assert b"16 16 20" in client.get(reverse("core:home")).content  # midnight paper
