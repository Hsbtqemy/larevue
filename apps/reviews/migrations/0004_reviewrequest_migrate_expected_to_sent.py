from django.db import migrations


def migrate_expected_to_sent(apps, schema_editor):
    ReviewRequest = apps.get_model("reviews", "ReviewRequest")
    ReviewRequest.objects.filter(state="expected").update(state="sent")


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0003_reviewrequest_add_states_sent_at"),
    ]

    operations = [
        migrations.RunPython(migrate_expected_to_sent, migrations.RunPython.noop),
    ]
