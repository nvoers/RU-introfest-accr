"""Items and zones that people earn per shift.

A team (or a single shift) points to a credential. For every shift a person has, that
credential's zones and default items are added on top of their own credential:
payment card amounts are summed, other items are counted, zones are combined.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Q

from accreditation.models import Accreditation, AccreditationItem, Item


def tally(credentials):
    """Sum what these credentials give: (quantities, card amounts, zones) per item."""
    quantities, amounts, zones = defaultdict(int), defaultdict(Decimal), set()
    for package in credentials:
        zones.update(package.zones.all())
        for default in package.default_items.select_related("item"):
            if default.item.is_payment_card:
                amounts[default.item] += default.card_amount()
            else:
                quantities[default.item] += default.quantity
    return quantities, amounts, zones


def describe(credentials):
    """Readable summary, e.g. "Payment card €25.00, 1× Meal voucher · Backstage"."""
    from accreditation.models import money

    quantities, amounts, zones = tally(credentials)
    parts = [f"{item.name} {money(total)}" for item, total in amounts.items()]
    parts += [f"{n}× {item.name}" for item, n in quantities.items()]
    text = ", ".join(parts)
    if zones:
        zone_names = ", ".join(z.name for z in sorted(zones, key=lambda z: (z.order, z.name)))
        text = f"{text} · {zone_names}" if text else zone_names
    return text


def sync(person):
    assignments = person.shift_assignments.select_related(
        "shift__shift_credential", "shift__team__shift_credential"
    )
    packages = [c for a in assignments for c in a.shift.perks]
    by_item_q, by_item_a, zones = tally(packages)
    quantities = {item.pk: n for item, n in by_item_q.items()}
    amounts = {item.pk: total for item, total in by_item_a.items()}

    person.shift_zones.set(zones)
    earned = set(quantities) | set(amounts)
    existing = {h.item_id: h for h in person.items.select_related("item")}

    for item_id in earned:
        handout = existing.get(item_id)
        if handout is None:
            is_card = item_id in amounts
            handout = AccreditationItem(
                accreditation=person,
                item_id=item_id,
                quantity=1 if is_card else 0,
                amount=Decimal("0") if is_card else None,
                from_shifts=True,
            )
        handout.shift_quantity = quantities.get(item_id, 0)
        handout.shift_amount = amounts.get(item_id, Decimal("0"))
        handout.save()

    for item_id, handout in existing.items():
        if item_id in earned or not handout.has_shift_part:
            continue
        handout.shift_quantity, handout.shift_amount = 0, Decimal("0")
        own_part = handout.quantity if not handout.is_payment_card else handout.amount
        if handout.from_shifts and not own_part and not handout.is_issued:
            handout.delete()
        else:
            handout.save()


def sync_for_credential(credential):
    """Re-sync everyone whose shifts hand out this credential (after it was edited)."""
    people = Accreditation.objects.filter(
        Q(shift_assignments__shift__shift_credential=credential)
        | Q(shift_assignments__shift__team__shift_credential=credential)
    ).distinct()
    for person in people:
        sync(person)


def sync_shifts(shifts):
    people = Accreditation.objects.filter(shift_assignments__shift__in=shifts).distinct()
    for person in people:
        sync(person)
