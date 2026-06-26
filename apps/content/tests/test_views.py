import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.content.models import Category, Post, Status, Tag
from tests.factories import PostFactory

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="writer")


def test_post_list_shows_only_published(client, author):
    Post.objects.create(title="Draft", author=author)
    Post.objects.create(title="Live", author=author, status=Status.PUBLISHED)
    response = client.get(reverse("content:post_list"))
    assert response.status_code == 200
    assert b"Live" in response.content
    assert b"Draft" not in response.content


def test_post_list_has_no_n_plus_one(client):
    """The blog index query count must not grow with the number of posts.

    Rendering more posts (each with a parler translation + author) on the same
    page must not add queries — the regression that locks in `no N+1` on the
    hottest public list view. We compare two payload sizes rather than pinning an
    absolute count so the guard survives unrelated query-shape changes.
    """
    url = reverse("content:post_list")

    PostFactory.create_batch(2)
    # Warm the cached singletons (SiteSettings/SeoSettings/menus) first so the
    # measured requests differ only in post count, not cold-cache loads.
    client.get(url)
    with CaptureQueriesContext(connection) as few:
        assert client.get(url).status_code == 200

    PostFactory.create_batch(4)
    with CaptureQueriesContext(connection) as many:
        assert client.get(url).status_code == 200

    assert len(many.captured_queries) == len(few.captured_queries)


def test_published_post_detail_visible(client, author):
    post = Post.objects.create(title="Hello World", author=author, status=Status.PUBLISHED)
    response = client.get(post.get_absolute_url())
    assert response.status_code == 200
    assert b"Hello World" in response.content


def test_post_detail_has_breadcrumbs(client, author):
    """Detail pages carry an accessible breadcrumb trail (DESIGN_SYSTEM §5)."""
    post = Post.objects.create(title="Breadcrumbed", author=author, status=Status.PUBLISHED)
    html = client.get(post.get_absolute_url()).content.decode()
    assert 'aria-label="Breadcrumb"' in html
    assert ">Home<" in html
    assert ">Blog<" in html
    assert 'aria-current="page"' in html


def test_draft_hidden_from_anonymous(client, author):
    post = Post.objects.create(title="Secret", author=author)
    response = client.get(post.get_absolute_url())
    assert response.status_code == 404


def test_draft_previewable_by_editor(client, author):
    editor = User.objects.create_user(username="ed", password="pw")
    editor.groups.add(Group.objects.get(name="Editor"))  # has delete_post -> manages all
    client.force_login(editor)

    post = Post.objects.create(title="Preview Me", author=author)
    response = client.get(post.get_absolute_url())
    assert response.status_code == 200
    assert b"Draft preview" in response.content


def test_author_can_preview_own_draft(client, author):
    client.force_login(author)
    post = Post.objects.create(title="My Draft", author=author)
    assert client.get(post.get_absolute_url()).status_code == 200


def test_contributor_cannot_preview_others_draft(client, author):
    # Regression: Contributors hold change_post but must not read others' drafts.
    contributor = User.objects.create_user(username="contrib", password="pw")
    contributor.groups.add(Group.objects.get(name="Contributor"))
    client.force_login(contributor)

    post = Post.objects.create(title="Not Yours", author=author)
    assert client.get(post.get_absolute_url()).status_code == 404


def test_category_archive(client, author):
    cat = Category.objects.create(name="News")
    post = Post.objects.create(title="Newsy", author=author, status=Status.PUBLISHED)
    post.categories.add(cat)
    response = client.get(cat.get_absolute_url())
    assert response.status_code == 200
    assert b"Newsy" in response.content


def test_tag_archive(client, author):
    tag = Tag.objects.create(name="django")
    post = Post.objects.create(title="Tagged", author=author, status=Status.PUBLISHED)
    post.tags.add(tag)
    response = client.get(tag.get_absolute_url())
    assert response.status_code == 200
    assert b"Tagged" in response.content


# --------------------------------------------------------------------------- #
# Editorial reading experience (Phase 10.3)
# --------------------------------------------------------------------------- #
def test_post_detail_body_uses_prose_typography(client, author):
    """The article body is wrapped in the dp-prose long-form type style."""
    post = Post.objects.create(
        title="Readable", body="<p>Hello.</p>", author=author, status=Status.PUBLISHED
    )
    html = client.get(post.get_absolute_url()).content
    assert b"dp-prose" in html


def test_post_detail_chrome_has_no_em_dash(client, author):
    """No em-dash in the page chrome (the comment form 'Replying to' line)."""
    post = Post.objects.create(
        title="Clean", body="<p>x</p>", author=author, status=Status.PUBLISHED
    )
    html = client.get(post.get_absolute_url()).content.decode()
    assert "—" not in html


def test_comment_form_uses_button_primitive(client, author):
    """The public comment form's submit uses the shared dp-btn primitive."""
    post = Post.objects.create(
        title="Talk", body="<p>x</p>", author=author, status=Status.PUBLISHED
    )
    html = client.get(post.get_absolute_url()).content
    assert b"dp-btn-primary" in html
