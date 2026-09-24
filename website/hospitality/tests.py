from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Types


class HospitalityTypeTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user("crew", password="pw"))
        self.url = reverse("hospitality_list")

    def post_new(self, **data):
        return self.client.post(
            self.url,
            {"action": "create", **{f"type-new-{k}": v for k, v in data.items()}},
        )

    def test_coin_value_forced_to_one(self):
        self.post_new(name="Drink coin", type="coin", value="5")
        self.assertEqual(Types.objects.get(name="Drink coin").value, 1)

    def test_voucher_value_forced_to_zero(self):
        self.post_new(name="Dinner", type="none", value="")
        self.assertEqual(Types.objects.get(name="Dinner").value, 0)

    def test_card_needs_value(self):
        response = self.post_new(name="Card", type="card", value="")
        self.assertContains(response, "greater than 0")
        self.assertContains(response, 'data-open-dialog="dlg-type-new"')
        self.post_new(name="Card", type="card", value="7.50")
        self.assertEqual(str(Types.objects.get(name="Card").value), "7.50")

    def test_edit_and_delete(self):
        item = Types.objects.create(name="Old", type="coin", value=1)
        self.client.post(
            self.url,
            {
                "action": "update",
                "item": item.pk,
                f"type-{item.pk}-name": "New",
                f"type-{item.pk}-type": "coin",
                f"type-{item.pk}-value": "",
            },
        )
        item.refresh_from_db()
        self.assertEqual(item.name, "New")
        self.client.post(self.url, {"action": "delete", "item": item.pk})
        self.assertFalse(Types.objects.exists())
