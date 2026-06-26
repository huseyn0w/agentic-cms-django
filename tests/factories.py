"""Shared factory_boy factories for terse, intent-revealing test setup.

The project deliberately keeps its data layer ORM-idiomatic, so these factories
are thin wrappers over the managers' ``create`` — they exist to remove repeated
boilerplate (a valid author, a publishable post) from tests that don't care about
the exact field values, not to hide the ORM. Parler-translated fields (``title``,
``body``, ``excerpt``) are accepted as plain kwargs because parler resolves them
through ``Model.objects.create`` exactly like a non-translated field.
"""

from __future__ import annotations

import factory
from django.contrib.auth import get_user_model

from apps.content.models import Post, Status

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = "Test"

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        # Always hash a usable password so the factory user can authenticate.
        self.set_password(extracted or "pw-secret-123")
        if create:
            self.save(update_fields=["password"])


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    title = factory.Sequence(lambda n: f"Factory Post {n}")
    excerpt = "A factory-built post."
    body = "<p>Body built by the factory.</p>"
    status = Status.PUBLISHED
    author = factory.SubFactory(UserFactory)
