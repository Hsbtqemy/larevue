from django.db import migrations, models


VALID_CHOICES = {"terracotta", "olive", "slate", "plum", "ochre"}


def normalize_accent_color(apps, schema_editor):
    Journal = apps.get_model("journals", "Journal")
    Journal.objects.exclude(accent_color__in=VALID_CHOICES).update(accent_color="terracotta")


class Migration(migrations.Migration):

    dependencies = [
        ("journals", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="journal",
            name="accent_color",
            field=models.CharField(
                choices=[
                    ("terracotta", "Terracotta"),
                    ("olive", "Olive"),
                    ("slate", "Ardoise"),
                    ("plum", "Prune"),
                    ("ochre", "Ocre"),
                ],
                default="terracotta",
                max_length=20,
                verbose_name="Couleur d'accentuation",
            ),
        ),
        migrations.RunPython(normalize_accent_color, migrations.RunPython.noop),
    ]
