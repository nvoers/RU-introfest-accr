from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accreditation import services
from accreditation.models import Accreditation, AccreditationItem, AccreditationType, Item, TypeItem
from core.models import Event


class PaymentCardTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("org", password="pw"))
        today = timezone.localdate()
        self.event = Event.objects.create(name="Fest", start_date=today, end_date=today + timedelta(days=1))
        self.card = Item.objects.create(
            event=self.event, name="Payment card", kind=Item.PAYMENT_CARD, default_amount=Decimal("10")
        )
        self.artist = AccreditationType.objects.create(event=self.event, name="Artist")
        self.crew = AccreditationType.objects.create(event=self.event, name="Crew")

    def url(self, name, *args):
        return reverse(name, args=[self.event.slug, *args])

    def person(self, type_, **kw):
        acc = Accreditation.objects.create(event=self.event, type=type_, first_name="Eva", **kw)
        acc.apply_default_items()
        return acc

    def test_amount_from_credential_or_item_default(self):
        TypeItem.objects.create(type=self.artist, item=self.card, amount=Decimal("25"))
        TypeItem.objects.create(type=self.crew, item=self.card)  # no override -> item default
        self.assertEqual(self.person(self.artist).items.get().amount, Decimal("25"))
        self.assertEqual(self.person(self.crew).items.get().amount, Decimal("10"))

    def test_credential_form_sets_card_amount_and_empty_removes_it(self):
        data = {"f-{}-name".format(self.artist.pk): "Artist", f"f-{self.artist.pk}-color": "#000000",
                f"f-{self.artist.pk}-order": 0, "item": self.artist.pk,
                f"f-{self.artist.pk}-item_{self.card.pk}": "30.50"}
        self.client.post(self.url("types"), data)
        self.assertEqual(TypeItem.objects.get(type=self.artist).amount, Decimal("30.50"))
        data[f"f-{self.artist.pk}-item_{self.card.pk}"] = ""
        self.client.post(self.url("types"), data)
        self.assertFalse(TypeItem.objects.filter(type=self.artist).exists())

    def test_item_form_requires_amount_for_cards_only(self):
        response = self.client.post(self.url("items"), {"f-new-name": "Card 2", "f-new-kind": "payment_card"})
        self.assertContains(response, "Set the standard amount")
        self.client.post(self.url("items"), {"f-new-name": "Band", "f-new-kind": "wristband",
                                             "f-new-default_amount": "5"})
        self.assertIsNone(Item.objects.get(name="Band").default_amount)

    def test_set_amount_per_person(self):
        TypeItem.objects.create(type=self.artist, item=self.card, amount=Decimal("25"))
        acc = self.person(self.artist)
        handout = acc.items.get()
        self.client.post(self.url("person_detail", acc.pk),
                         {"action": "item_amount", "handout": handout.pk, "amount": "42,50"})
        handout.refresh_from_db()
        self.assertEqual(handout.amount, Decimal("42.50"))
        self.client.post(self.url("person_detail", acc.pk),
                         {"action": "item_amount", "handout": handout.pk, "amount": "-3"})
        handout.refresh_from_db()
        self.assertEqual(handout.amount, Decimal("42.50"))

    def test_add_card_to_person_with_amount(self):
        acc = self.person(self.crew)
        self.client.post(self.url("person_detail", acc.pk),
                         {"action": "item_add", "item": self.card.pk, "quantity": 1, "amount": "12"})
        self.assertEqual(acc.items.get().amount, Decimal("12"))

    def test_bulk_set_card(self):
        a, b = self.person(self.crew), self.person(self.crew)
        TypeItem.objects.create(type=self.crew, item=self.card)
        b.apply_default_items()
        self.client.post(self.url("people"), {"ids": [a.pk, b.pk], "bulk": "card",
                                              "card_item": self.card.pk, "card_amount": "17.5"})
        amounts = set(AccreditationItem.objects.filter(item=self.card).values_list("amount", flat=True))
        self.assertEqual(amounts, {Decimal("17.50")})
        self.assertEqual(AccreditationItem.objects.filter(item=self.card).count(), 2)

    def test_amount_shown_on_ticket_scanner_and_export(self):
        TypeItem.objects.create(type=self.artist, item=self.card, amount=Decimal("25"))
        acc = self.person(self.artist, status="approved")
        self.assertContains(self.client.get(reverse("ticket", args=[acc.token])), "Payment card · €25.00")
        self.assertIn("€25.00", services.process_scan(self.event, acc.token)["items"][0]["label"])
        export = self.client.get(self.url("people_export")).content.decode("utf-8-sig")
        self.assertIn("25.00", export)
        self.assertContains(self.client.get(self.url("people")), "€25.00")

    def test_existing_item_converted_to_payment_card(self):
        old = Item.objects.create(event=self.event, name="Card", kind=Item.VOUCHER)
        TypeItem.objects.create(type=self.crew, item=old, quantity=25)
        acc = self.person(self.crew)
        self.client.post(self.url("items"), {
            "item": old.pk, f"f-{old.pk}-name": "Card", f"f-{old.pk}-kind": "payment_card",
            f"f-{old.pk}-default_amount": "12.50",
        })
        default = TypeItem.objects.get(type=self.crew, item=old)
        self.assertEqual((default.quantity, default.card_amount()), (1, Decimal("12.50")))
        self.assertEqual(acc.items.get(item=old).amount, Decimal("12.50"))
