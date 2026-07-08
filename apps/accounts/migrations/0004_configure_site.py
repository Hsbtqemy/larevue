from django.conf import settings
from django.db import migrations

# Valeurs canoniques du site (utilisées par django.contrib.sites pour construire
# les URLs absolues et le nom affiché dans les emails allauth : reset de mot de
# passe, etc.). Sans ça, l'enregistrement Site reste sur les valeurs par défaut
# « example.com » installées par Django.
SITE_DOMAIN = "www.edito-revue.fr"
SITE_NAME = "Edito"

DEFAULT_DOMAIN = "example.com"
DEFAULT_NAME = "example.com"


def set_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": SITE_DOMAIN, "name": SITE_NAME},
    )


def reset_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": DEFAULT_DOMAIN, "name": DEFAULT_NAME},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_reviewer_role_and_contact_link"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_site, reset_site),
    ]
