from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from accreditation.models import Accreditation, AccreditationType

from . import perks
from .models import ShiftAssignment


@receiver(post_save, sender=ShiftAssignment)
@receiver(post_delete, sender=ShiftAssignment)
def update_perks(sender, instance, **kwargs):
    person = Accreditation.objects.filter(pk=instance.person_id).first()
    if person is not None:  # gone when the person itself is being deleted
        perks.sync(person)


@receiver(pre_delete, sender=AccreditationType)
def remember_people(sender, instance, **kwargs):
    """A credential that shifts hand out is being deleted: remember who to re-sync."""
    instance._shift_people = list(
        Accreditation.objects.filter(
            Q(shift_assignments__shift__shift_credential=instance)
            | Q(shift_assignments__shift__team__shift_credential=instance)
        ).distinct()
    )


@receiver(post_delete, sender=AccreditationType)
def resync_people(sender, instance, **kwargs):
    for person in getattr(instance, "_shift_people", []):
        perks.sync(person)
