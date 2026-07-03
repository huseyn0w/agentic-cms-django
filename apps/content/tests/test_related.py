"""Related posts by shared taxonomy (§1).

Target: a "Related posts" block on post detail showing published posts that share
a category or tag with the current post, excluding the current post, capped.
"""

import pytest
from django.contrib.auth import get_user_model

from apps.content.models import Category, Post, Status, Tag
from apps.content.repositories import PostRepository
from apps.content.services import related_posts

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def author():
    return User.objects.create_user(username="w")


def _pub(title, author, **kw):
    return Post.objects.create(title=title, author=author, status=Status.PUBLISHED, **kw)


def test_related_by_shared_category(author):
    cat = Category.objects.create(name="Django", slug="django")
    current = _pub("Current", author)
    current.categories.add(cat)
    other = _pub("Other", author)
    other.categories.add(cat)
    unrelated = _pub("Unrelated", author)

    related = list(related_posts(current))
    assert other in related
    assert unrelated not in related
    assert current not in related  # never includes itself


def test_related_by_shared_tag(author):
    tag = Tag.objects.create(name="Tips", slug="tips")
    current = _pub("Current", author)
    current.tags.add(tag)
    other = _pub("Other", author)
    other.tags.add(tag)

    assert other in list(related_posts(current))


def test_related_excludes_drafts(author):
    cat = Category.objects.create(name="C", slug="c")
    current = _pub("Current", author)
    current.categories.add(cat)
    draft = Post.objects.create(title="Draft", author=author, status=Status.DRAFT)
    draft.categories.add(cat)

    assert draft not in list(related_posts(current))


def test_related_is_capped(author):
    cat = Category.objects.create(name="C", slug="c")
    current = _pub("Current", author)
    current.categories.add(cat)
    for i in range(6):
        p = _pub(f"P{i}", author)
        p.categories.add(cat)

    assert len(list(related_posts(current, limit=3))) == 3


def test_related_deduplicates_across_category_and_tag(author):
    """A post sharing BOTH a category and a tag appears once, not twice."""
    cat = Category.objects.create(name="C", slug="c")
    tag = Tag.objects.create(name="T", slug="t")
    current = _pub("Current", author)
    current.categories.add(cat)
    current.tags.add(tag)
    both = _pub("Both", author)
    both.categories.add(cat)
    both.tags.add(tag)

    related = list(related_posts(current))
    assert related.count(both) == 1


def test_repository_related_by_taxonomy_available(author):
    cat = Category.objects.create(name="C", slug="c")
    current = _pub("Current", author)
    current.categories.add(cat)
    other = _pub("Other", author)
    other.categories.add(cat)
    assert other in list(PostRepository.related_by_taxonomy(current, limit=5))


def test_related_block_rendered_on_post_detail(client, author):
    cat = Category.objects.create(name="C", slug="c")
    current = _pub("Current", author)
    current.categories.add(cat)
    other = _pub("Neighbour", author)
    other.categories.add(cat)

    html = client.get(current.get_absolute_url()).content.decode()
    assert "Related posts" in html
    assert "Neighbour" in html


def test_no_related_block_when_none_shared(client, author):
    current = _pub("Solo", author)
    html = client.get(current.get_absolute_url()).content.decode()
    # The block only renders when there ARE related posts (no empty section).
    assert "Related posts" not in html
