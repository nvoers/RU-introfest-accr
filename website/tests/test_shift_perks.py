from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accreditation.models import Accreditation, AccreditationType, Item, TypeItem, Zone
from core.models import Event, Membership
from crew.models import Shift, ShiftAssignment, Team


class ShiftPerkTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("org", password="pw")
        self.client.force_login(user)
        today = timezone.localdate()
        self.event = Event.objects.create(name="Fest", start_date=today, end_date=today + timedelta(days=1))
        Membership.objects.create(user=user, event=self.event, role="manager")
        self.day = self.event.days.first()
        self.card = Item.objects.create(event=self.event, name="Card", kind=Item.PAYMENT_CARD,
                                        default_amount=Decimal("0"))
        self.meal = Item.objects.create(event=self.event, name="Meal", kind=Item.VOUCHER)
        self.backstage = Zone.objects.create(event=self.event, name="Backstage")

        def credential(name, items, zones=()):
            t = AccreditationType.objects.create(event=self.event, name=name)
            t.zones.set(zones)
            for item, value in items:
                if item.is_payment_card:
                    TypeItem.objects.create(type=t, item=item, quantity=1, amount=Decimal(value))
                else:
                    TypeItem.objects.create(type=t, item=item, quantity=value)
            return t

        self.volunteer = credential("Volunteer", [])
        self.bar_shift = credential("Bar shift", [(self.meal, 1)])
        self.disco_shift = credential("Disco shift", [(self.card, "12.50")], [self.backstage])
        # Extra on top of the team's €12.50 for the dinner shift.
        self.dinner_shift = credential("Disco dinner extra", [(self.card, "12.50")])

        self.bar = Team.objects.create(event=self.event, name="Bar", shift_credential=self.bar_shift)
        self.disco = Team.objects.create(event=self.event, name="Silent disco", shift_credential=self.disco_shift)
        self.disco_1 = self.shift(self.disco, 12, 16)
        self.disco_dinner = self.shift(self.disco, 16, 20, credential=self.dinner_shift)
        self.bar_1 = self.shift(self.bar, 12, 14)
        self.bar_2 = self.shift(self.bar, 20, 22)
        self.person = Accreditation.objects.create(event=self.event, type=self.volunteer,
                                                   first_name="Vera", status="approved")

    def shift(self, team, start, end, credential=None):
        return Shift.objects.create(team=team, day=self.day, start=time(start), end=time(end),
                                    capacity=5, shift_credential=credential)

    def assign(self, *shifts):
        for s in shifts:
            ShiftAssignment.objects.create(shift=s, person=self.person)

    def card_total(self):
        return self.person.items.get(item=self.card).total_amount

    def test_card_amounts_add_up_per_shift(self):
        self.assign(self.disco_1)
        self.assertEqual(self.card_total(), Decimal("12.50"))
        self.assign(self.disco_dinner)
        self.assertEqual(self.card_total(), Decimal("37.50"))

    def test_items_count_per_shift_and_zones_combine(self):
        self.assign(self.bar_1, self.bar_2)
        self.assertEqual(self.person.items.get(item=self.meal).total_quantity, 2)
        self.assertNotIn(self.backstage, self.person.all_zones())
        self.assign(self.disco_1)
        self.assertIn(self.backstage, self.person.all_zones())

    def test_dropping_shift_removes_its_perks(self):
        self.assign(self.disco_1, self.disco_dinner)
        ShiftAssignment.objects.get(shift=self.disco_dinner).delete()
        self.assertEqual(self.card_total(), Decimal("12.50"))
        ShiftAssignment.objects.get(shift=self.disco_1).delete()
        self.assertFalse(self.person.items.filter(item=self.card).exists())
        self.assertEqual(self.person.shift_zones.count(), 0)

    def test_own_amount_is_kept_on_top(self):
        self.assign(self.disco_1)
        handout = self.person.items.get(item=self.card)
        handout.amount = Decimal("5")
        handout.save()
        ShiftAssignment.objects.get(shift=self.disco_1).delete()
        handout.refresh_from_db()
        self.assertEqual(handout.total_amount, Decimal("5"))

    def test_issued_items_are_not_deleted(self):
        self.assign(self.bar_1)
        meal = self.person.items.get(item=self.meal)
        meal.issued_at = timezone.now()
        meal.save()
        ShiftAssignment.objects.get(shift=self.bar_1).delete()
        self.assertTrue(self.person.items.filter(item=self.meal).exists())

    def test_changing_team_perks_updates_people(self):
        self.assign(self.bar_1)
        url = reverse("teams", args=[self.event.slug])
        self.client.post(url, {"item": self.bar.pk, f"f-{self.bar.pk}-name": "Bar",
                               f"f-{self.bar.pk}-color": "#000000",
                               f"f-{self.bar.pk}-shift_credential": self.disco_shift.pk})
        self.assertEqual(self.card_total(), Decimal("12.50"))
        self.assertFalse(self.person.items.filter(item=self.meal).exists())

    def test_editing_credential_amount_updates_people(self):
        self.assign(self.disco_1)
        url = reverse("types", args=[self.event.slug])
        pk = self.disco_shift.pk
        self.client.post(url, {"item": pk, f"f-{pk}-name": "Disco shift", f"f-{pk}-color": "#000000",
                               f"f-{pk}-order": 0, f"f-{pk}-zones": [self.backstage.pk],
                               f"f-{pk}-item_{self.card.pk}": "15", f"f-{pk}-item_{self.meal.pk}": 0})
        self.assertEqual(self.card_total(), Decimal("15.00"))

    def test_volunteer_claim_from_ticket_page(self):
        self.client.logout()
        self.client.post(reverse("ticket", args=[self.person.token]),
                         {"action": "claim", "shift": self.disco_dinner.pk})
        self.assertEqual(self.card_total(), Decimal("25.00"))
        response = self.client.get(reverse("ticket", args=[self.person.token]))
        self.assertContains(response, "Card · €25.00")
        self.assertContains(response, "You get: Card €25.00")

    def test_deleting_person_with_shifts(self):
        self.assign(self.disco_1)
        self.person.delete()
        self.assertFalse(Accreditation.objects.exists())

    def test_item_default_change_updates_shift_cards(self):
        TypeItem.objects.filter(type=self.disco_shift).update(amount=None)  # use item default
        self.card.default_amount = Decimal("8")
        self.card.save()
        self.assign(self.disco_1)
        self.assertEqual(self.card_total(), Decimal("8"))
        url = reverse("items", args=[self.event.slug])
        pk = self.card.pk
        self.client.post(url, {"item": pk, f"f-{pk}-name": "Card", f"f-{pk}-kind": "payment_card",
                               f"f-{pk}-default_amount": "10"})
        self.assertEqual(self.card_total(), Decimal("10"))

    def test_person_page_shows_total_and_breakdown(self):
        handout_own = Decimal("12.50")
        self.assign(self.disco_1)
        h = self.person.items.get(item=self.card)
        h.amount = handout_own
        h.save()
        response = self.client.get(reverse("person_detail", args=[self.event.slug, self.person.pk]))
        self.assertContains(response, "€25.00</b>")
        self.assertContains(response, "€12.50 own + €12.50 from shifts")

    def test_shift_extra_adds_to_team(self):
        self.assign(self.disco_dinner)
        self.assertEqual(self.card_total(), Decimal("25.00"))
        self.assertIn(self.backstage, self.person.all_zones())  # zone from the team's credential
        self.assertEqual(self.disco_dinner.perk_text, "Card €25.00 · Backstage")
