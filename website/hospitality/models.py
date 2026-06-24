from django.db import models
from django.core.exceptions import ValidationError


class Types(models.Model):
    name = models.CharField(max_length=200, unique=True)
    CARD = "card"
    COIN = "coin"
    NONE = "none"
    type_choices = {
        CARD: "Card",
        COIN: "Coin",
        NONE: "None",
    }
    type = models.CharField(choices=type_choices.items(), max_length=10, default=NONE)
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Only for card type: the value of the card. For coin type, the value is always 1. For none type, the value is 0.",
    )

    def __str__(self):
        return self.name

    def clean(self):
        if self.type == self.COIN:
            self.value = 1
        elif self.type == self.NONE:
            self.value = 0
        if self.type == self.CARD and self.value <= 0:
            raise ValidationError("Card type must have a value greater than 0.")

    class Meta:
        verbose_name_plural = "Types"


class HospitalityEntry(models.Model):
    entry = models.ForeignKey("accreditatie.AccessEntry", on_delete=models.CASCADE)
    type = models.ForeignKey(
        Types, on_delete=models.CASCADE, default=None, null=True, blank=True
    )
    amount = models.PositiveIntegerField(
        default=1, help_text="Number of items per person in entry"
    )

    ISSUED = "issued"
    NOT_ISSUED = "not_issued"
    STATUS_CHOICES = {
        ISSUED: "Issued",
        NOT_ISSUED: "Not Issued",
    }
    status = models.CharField(
        choices=STATUS_CHOICES.items(), max_length=15, default=NOT_ISSUED
    )

    def __str__(self):
        return f"{self.type.name} - {self.entry.name}"

    class Meta:
        verbose_name_plural = "Hospitality Entries"


class Space(models.Model):
    name = models.CharField(max_length=200, unique=False)
    event = models.ForeignKey(
        "accreditatie.Event",
        on_delete=models.CASCADE,
        default=None,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name} - {self.event.name}"


class SpaceEntry(models.Model):
    entry = models.ForeignKey("accreditatie.AccessEntry", on_delete=models.CASCADE)
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, default=None, null=True, blank=True
    )

    def __str__(self):
        return f"{self.entry.name} - {self.space.name}"

    class Meta:
        verbose_name_plural = "Space Entries"


class RiderEntry(models.Model):
    entry = models.ForeignKey("accreditatie.AccessEntry", on_delete=models.CASCADE)
    rider = models.TextField()

    def __str__(self):
        return f"{self.entry.name} - Rider Entry"

    class Meta:
        verbose_name_plural = "Rider Entries"
