from django.db import models
from django.core.exceptions import ValidationError


class Event(models.Model):
    name = models.CharField(max_length=200, unique=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Events"


class Entrance(models.Model):
    name = models.CharField(max_length=200, unique=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, default=None, null=True, blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Entrances"


class AccessLevel(models.Model):
    name = models.CharField(max_length=200, unique=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, default=None, null=True, blank=True
    )
    color = models.CharField(
        max_length=7, default="#000000", help_text="Hex color code"
    )  # Hex color code

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Access Levels"


class AccessEntry(models.Model):
    name = models.CharField(max_length=200)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        default=None,
        null=True,
        blank=True,
        related_name="access_entries",
    )

    ARTIST = "Artist"
    CREW = "Crew"
    GUEST = "Guest"
    access_types = {
        ARTIST: "Artist",
        CREW: "Crew",
        GUEST: "Guest",
    }
    access_type = models.CharField(
        choices=access_types.items(), max_length=10, default=CREW
    )
    number_of_tickets = models.PositiveIntegerField(default=1)
    entrance = models.ForeignKey(
        Entrance, on_delete=models.CASCADE, default=None, null=True, blank=True
    )
    access_level = models.ForeignKey(
        AccessLevel, on_delete=models.CASCADE, default=None, null=True, blank=True
    )

    ARRIVED = "Arrived"
    NOT_ARRIVED = "Not Arrived"
    CANCELLED = "Cancelled"
    status_choices = {
        ARRIVED: "Arrived",
        NOT_ARRIVED: "Not Arrived",
        CANCELLED: "Cancelled",
    }
    status = models.CharField(
        choices=status_choices.items(), max_length=15, default=NOT_ARRIVED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.event.name}"

    class Meta:
        verbose_name = "Access Entry"
        verbose_name_plural = "Access Entries"

    def clean(self):
        if self.number_of_tickets < 1:
            raise ValidationError("Number of tickets must be at least 1.")
        if self.entrance and self.entrance.event != self.event:
            raise ValidationError(
                "Entrance must belong to the same event as the access entry."
            )
