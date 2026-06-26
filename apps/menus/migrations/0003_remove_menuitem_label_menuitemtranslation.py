# Convert MenuItem.label (a plain column) to a parler translated field while
# PRESERVING existing labels. Ordering matters and avoids a name clash:
#   1. rename label -> legacy_label  (frees the `label` name for parler)
#   2. create the MenuItemTranslation table (parler overlays translated `label`)
#   3. copy each legacy_label into the default-language translation
#   4. drop legacy_label
# All steps go through the ORM (no raw SQL, DB-agnostic).

import django.db.models.deletion
import parler.fields
import parler.models
from django.conf import settings
from django.db import migrations, models


def copy_labels_to_translations(apps, schema_editor):
    """Move every item's existing label into its default-language translation."""
    MenuItem = apps.get_model("menus", "MenuItem")
    MenuItemTranslation = apps.get_model("menus", "MenuItemTranslation")
    language = settings.LANGUAGE_CODE
    rows = [
        MenuItemTranslation(master_id=pk, language_code=language, label=label)
        for pk, label in MenuItem.objects.values_list("pk", "legacy_label")
        if label
    ]
    MenuItemTranslation.objects.bulk_create(rows)


def restore_labels_from_translations(apps, schema_editor):
    """Reverse: copy the default-language label back onto legacy_label.

    Operations reverse last-to-first, so by the time this runs the RemoveField has
    already re-added the column under its ORIGINAL name ``legacy_label`` (the
    RenameField that turns it back into ``label`` reverses LAST). Write
    ``legacy_label`` here, not ``label``.
    """
    MenuItem = apps.get_model("menus", "MenuItem")
    MenuItemTranslation = apps.get_model("menus", "MenuItemTranslation")
    language = settings.LANGUAGE_CODE
    for translation in MenuItemTranslation.objects.filter(language_code=language):
        MenuItem.objects.filter(pk=translation.master_id).update(legacy_label=translation.label)


class Migration(migrations.Migration):

    dependencies = [
        ("menus", "0002_menuitem_parent"),
    ]

    operations = [
        migrations.RenameField(
            model_name="menuitem",
            old_name="label",
            new_name="legacy_label",
        ),
        migrations.CreateModel(
            name="MenuItemTranslation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "language_code",
                    models.CharField(db_index=True, max_length=15, verbose_name="Language"),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        help_text="Leave blank to use the linked item's title.",
                        max_length=80,
                        verbose_name="label",
                    ),
                ),
                (
                    "master",
                    parler.fields.TranslationsForeignKey(
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translations",
                        to="menus.menuitem",
                    ),
                ),
            ],
            options={
                "verbose_name": "menu item Translation",
                "db_table": "menus_menuitem_translation",
                "db_tablespace": "",
                "managed": True,
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("language_code", "master"),
                        name="menus_menuitem_translation_uniq_lang",
                    )
                ],
            },
            bases=(parler.models.TranslatedFieldsModelMixin, models.Model),
        ),
        migrations.RunPython(copy_labels_to_translations, restore_labels_from_translations),
        migrations.RemoveField(
            model_name="menuitem",
            name="legacy_label",
        ),
    ]
