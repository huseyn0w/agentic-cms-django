"""Read serializers for the public API.

Plain ``Serializer`` classes (not ``ModelSerializer``) because the translated
fields live on parler translation tables: attribute access (``obj.title``) returns
the active language, which is what we want to expose. List serializers omit the
heavy body; detail serializers add it.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.content import services as content_services
from apps.content.models import Status


class _TaxonomySerializer(serializers.Serializer):
    slug = serializers.CharField()
    name = serializers.CharField()


class AuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="display_name")
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return obj.get_absolute_url()


class PostSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    title = serializers.CharField()
    excerpt = serializers.CharField()
    published_at = serializers.DateTimeField()
    url = serializers.SerializerMethodField()
    author = AuthorSerializer(allow_null=True)
    categories = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return obj.get_absolute_url()

    def get_categories(self, obj) -> list[dict]:
        return _TaxonomySerializer(obj.categories.all(), many=True).data

    def get_tags(self, obj) -> list[dict]:
        return _TaxonomySerializer(obj.tags.all(), many=True).data


class PostDetailSerializer(PostSerializer):
    body = serializers.CharField()


class PostWriteSerializer(serializers.Serializer):
    """Create/update payload for the gated post API.

    Persistence + publish-gating go through ``content.services`` (which uses the
    repository), so no ORM lives in the serializer; translated fields land in the
    request's active language.
    """

    id = serializers.IntegerField(read_only=True)
    slug = serializers.SlugField(max_length=200, required=False, allow_blank=True)
    title = serializers.CharField(max_length=200)
    excerpt = serializers.CharField(required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Status.choices, required=False, default=Status.DRAFT)

    def create(self, validated_data):
        return content_services.api_create_post(validated_data, self.context["request"].user)

    def update(self, instance, validated_data):
        return content_services.api_update_post(
            instance, validated_data, self.context["request"].user
        )


class PageSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    title = serializers.CharField()
    published_at = serializers.DateTimeField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return obj.get_absolute_url()


class PageDetailSerializer(PageSerializer):
    body = serializers.CharField()


class ServiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    title = serializers.CharField()
    summary = serializers.CharField()
    price = serializers.CharField()
    published_at = serializers.DateTimeField()
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return obj.get_absolute_url()


class ServiceDetailSerializer(ServiceSerializer):
    description = serializers.CharField()
    area_served = serializers.CharField()
    faq = serializers.SerializerMethodField()

    def get_faq(self, obj) -> list[dict]:
        return [{"question": q, "answer": a} for q, a in obj.faq_items()]


class CategorySerializer(_TaxonomySerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return obj.get_absolute_url()


class TagSerializer(_TaxonomySerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, obj) -> str:
        return obj.get_absolute_url()
