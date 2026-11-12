from django.db import migrations


def grant_existing(apps, schema_editor):
    """Before roles existed every user could do everything: keep that for existing users."""
    User = apps.get_model("auth", "User")
    Event = apps.get_model("core", "Event")
    Membership = apps.get_model("core", "Membership")
    events = list(Event.objects.all())
    for user in User.objects.filter(is_active=True, is_superuser=False):
        for event in events:
            Membership.objects.get_or_create(user=user, event=event, defaults={"role": "manager"})


class Migration(migrations.Migration):
    dependencies = [("core", "0002_memberships")]
    operations = [migrations.RunPython(grant_existing, migrations.RunPython.noop)]
