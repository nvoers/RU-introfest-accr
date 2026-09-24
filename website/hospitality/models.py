from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Types(models.Model):
    CARD = "card"
    COIN = "coin"
    NONE = "none"
    type_choices = {
        COIN: "Coin",
        CARD: "Card",
        NONE: "Voucher",
    }

    name = models.CharField(max_length=200, unique=True)
    type = models.CharField(
        "kind", choices=type_choices.items(), max_length=10, default=NONE
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Card value in euros. Coins are always worth 1, vouchers 0.",
    )

    class Meta:
        verbose_name = "Hospitality item"
        verbose_name_plural = "Hospitality items"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.type == self.COIN:
            self.value = Decimal(1)
        elif self.type == self.NONE:
            self.value = Decimal(0)
        elif self.type == self.CARD and (self.value is None or self.value <= 0):
            raise ValidationError({"value": "A card needs a value greater than 0."})


class HospitalityEntry(models.Model):
    ISSUED = "issued"
    NOT_ISSUED = "not_issued"
    STATUS_CHOICES = {
        ISSUED: "Issued",
        NOT_ISSUED: "Not issued",
    }

    entry = models.ForeignKey(
        "accreditatie.AccessEntry",
        on_delete=models.CASCADE,
        related_name="hospitality_items",
    )
    type = models.ForeignKey(
        Types,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="allocations",
        verbose_name="item",
    )
    amount = models.PositiveIntegerField(
        "per person", default=1, help_text="Number of items per person in entry"
    )
    status = models.CharField(
        choices=STATUS_CHOICES.items(), max_length=15, default=NOT_ISSUED
    )

    class Meta:
        verbose_name_plural = "Hospitality Entries"
        ordering = ["type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "type"], name="unique_hospitality_item_per_entry"
            )
        ]

    def __str__(self):
        return f"{self.type} - {self.entry.name}"

    @property
    def is_issued(self):
        return self.status == self.ISSUED

    @property
    def total(self):
        return self.amount * self.entry.number_of_tickets


class Space(models.Model):
    name = models.CharField(max_length=200)
    event = models.ForeignKey(
        "accreditatie.Event",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="spaces",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                "event", Lower("name"), name="unique_space_name_per_event"
            )
        ]

    def __str__(self):
        return self.name


class SpaceEntry(models.Model):
    entry = models.ForeignKey(
        "accreditatie.AccessEntry", on_delete=models.CASCADE, related_name="space_entry"
    )
    space = models.ForeignKey(
        Space,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="space_entry",
    )

    class Meta:
        verbose_name_plural = "Space Entries"
        ordering = ["space__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "space"], name="unique_space_per_entry"
            )
        ]

    def __str__(self):
        return f"{self.entry.name} - {self.space}"


class RiderEntry(models.Model):
    entry = models.ForeignKey(
        "accreditatie.AccessEntry",
        on_delete=models.CASCADE,
        related_name="rider_items",
    )
    rider = models.TextField()

    class Meta:
        verbose_name_plural = "Rider Entries"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.entry.name} - Rider Entry"
