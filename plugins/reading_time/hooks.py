"""Reading Time plugin — prepends an estimated reading time to each post body.

Demonstrates a `post_content` filter. The plugin slug ("reading_time") is inferred
from this module's path, so disabling the plugin in the admin skips this filter.
"""

from __future__ import annotations

import math

from django.utils.html import format_html, strip_tags

from apps.plugins.hooks import add_filter

WORDS_PER_MINUTE = 200


@add_filter("post_content")
def prepend_reading_time(html: str, post=None, **kwargs) -> str:
    word_count = len(strip_tags(html).split())
    minutes = max(1, math.ceil(word_count / WORDS_PER_MINUTE))
    badge = format_html(
        '<p class="mb-6 text-sm font-medium text-text-subtle">☕ {} min read</p>', minutes
    )
    return badge + html
