"""
Migration 0002 — Issue workflow v2 + deadline fields

Replaces the 6-state workflow (under_review, accepted, in_production,
sent_to_publisher, published, refused) with an 8-state workflow that adds
three intermediate phases:

  under_review → accepted → in_review → in_revision → final_check
                                                           ↓
                                                  sent_to_publisher → published
  under_review → refused  (terminal)

Also adds 5 optional deadline fields: deadline_articles, deadline_reviews,
deadline_v2, deadline_final_check, deadline_sent_to_publisher.

Data migration (forward)
------------------------
Rows with state='in_production' are mapped to 'accepted'. This is the
conservative choice: the original sub-state within the production phase
cannot be reconstructed from data alone, so we reset to the earliest
equivalent state and let the team re-advance manually.

Backward migration — APPROXIMATE, NOT FOR PRODUCTION USE
---------------------------------------------------------
The three new intermediate states (in_review, in_revision, final_check)
collapse back to 'in_production'. The original sub-state is permanently
lost. This backward path exists for theoretical reversibility during
development only; running it against a production database will lose
state information.
"""

import django_fsm
from django.db import migrations, models


def forward_migrate_states(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")
    Issue.objects.filter(state="in_production").update(state="accepted")


def backward_migrate_states(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")
    Issue.objects.filter(
        state__in=["in_review", "in_revision", "final_check"]
    ).update(state="in_production")


class Migration(migrations.Migration):

    dependencies = [
        ("issues", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="deadline_articles",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date limite articles",
                help_text="Date à laquelle tous les articles doivent être reçus.",
            ),
        ),
        migrations.AddField(
            model_name="issue",
            name="deadline_reviews",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date limite relectures",
                help_text="Date à laquelle toutes les relectures doivent être reçues.",
            ),
        ),
        migrations.AddField(
            model_name="issue",
            name="deadline_v2",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date limite V2",
                help_text="Date à laquelle les versions révisées doivent être reçues.",
            ),
        ),
        migrations.AddField(
            model_name="issue",
            name="deadline_final_check",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date limite vérification finale",
                help_text="Date limite pour la vérification finale avant envoi.",
            ),
        ),
        migrations.AddField(
            model_name="issue",
            name="deadline_sent_to_publisher",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Date limite envoi à l'éditeur",
                help_text="Date prévue d'envoi à l'éditeur.",
            ),
        ),
        migrations.RunPython(forward_migrate_states, backward_migrate_states),
        migrations.AlterField(
            model_name="issue",
            name="state",
            field=django_fsm.FSMField(
                choices=[
                    ("under_review", "En évaluation"),
                    ("accepted", "Accepté"),
                    ("in_review", "En attente des relectures"),
                    ("in_revision", "En attente des V2"),
                    ("final_check", "Vérification finale"),
                    ("sent_to_publisher", "Envoyé à l'éditeur"),
                    ("published", "Publié"),
                    ("refused", "Refusé"),
                ],
                default="under_review",
                max_length=50,
                protected=True,
                verbose_name="État",
            ),
        ),
    ]
