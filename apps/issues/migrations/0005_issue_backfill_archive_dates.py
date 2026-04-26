from django.db import migrations
from django.utils import timezone


def backfill_archive_dates(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")
    now = timezone.now()

    for issue in Issue.objects.filter(state="published", published_at__isnull=True):
        issue.published_at = issue.planned_publication_date or now
        issue.save(update_fields=["published_at"])

    for issue in Issue.objects.filter(state="refused", refused_at__isnull=True):
        issue.refused_at = now
        issue.save(update_fields=["refused_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("issues", "0004_issue_add_published_refused_at"),
    ]

    operations = [
        migrations.RunPython(backfill_archive_dates, migrations.RunPython.noop),
    ]
