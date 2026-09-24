from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Lower
from django.utils import timezone


class Event(models.Model):
    name = models.CharField(max_length=200, unique=True)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=200)

    class Meta:
        verbose_name_plural = "Events"
        ordering = ["-date", "name"]

    def __str__(self):
        return self.name

    @property
    def is_past(self):
        return self.date < timezone.localdate()

    def ticket_stats(self):
        """Ticket totals across all non-cancelled accreditations."""
        active = self.access_entries.exclude(status=AccessEntry.CANCELLED)
        totals = active.aggregate(
            total=Sum("number_of_tickets"),
            arrived=Sum(
                "number_of_tickets", filter=Q(status=AccessEntry.ARRIVED)
            ),
        )
        total = totals["total"] or 0
        arrived = totals["arrived"] or 0
        return {
            "entries": self.access_entries.count(),
            "cancelled": self.access_entries.filter(
                status=AccessEntry.CANCELLED
            ).count(),
            "tickets": total,
            "arrived": arrived,
            "expected": total - arrived,
            "percent": round(arrived / total * 100) if total else 0,
        }


class EventScopedModel(models.Model):
    """Something configured per event (entrance, access level, space)."""

    name = models.CharField(max_length=200)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Entrance(EventScopedModel):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="entrances",
    )

    class Meta(EventScopedModel.Meta):
        verbose_name_plural = "Entrances"
        constraints = [
            models.UniqueConstraint(
                "event", Lower("name"), name="unique_entrance_name_per_event"
            )
        ]


class AccessLevel(EventScopedModel):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_levels",
    )
    color = models.CharField(
        max_length=7, default="#000000", help_text="Hex color code"
    )

    class Meta(EventScopedModel.Meta):
        verbose_name_plural = "Access Levels"
        constraints = [
            models.UniqueConstraint(
                "event", Lower("name"), name="unique_access_level_name_per_event"
            )
        ]


class AccessEntry(models.Model):
    ARTIST = "Artist"
    CREW = "Crew"
    GUEST = "Guest"
    PRESS = "Press"
    SUPPLIER = "Supplier"
    access_types = {
        ARTIST: "Artist",
        CREW: "Crew",
        GUEST: "Guest",
        PRESS: "Press",
        SUPPLIER: "Supplier",
    }

    ARRIVED = "Arrived"
    NOT_ARRIVED = "Not Arrived"
    CANCELLED = "Cancelled"
    status_choices = {
        NOT_ARRIVED: "Not arrived",
        ARRIVED: "Arrived",
        CANCELLED: "Cancelled",
    }

    name = models.CharField(max_length=200)
    organisation = models.CharField(
        max_length=200, blank=True, help_text="Band, company or association"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_entries",
    )
    access_type = models.CharField(
        "type", choices=access_types.items(), max_length=10, default=CREW
    )
    number_of_tickets = models.PositiveIntegerField(
        "tickets", default=1, help_text="Number of people on this accreditation"
    )
    entrance = models.ForeignKey(
        Entrance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_entries",
    )
    access_level = models.ForeignKey(
        AccessLevel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_entries",
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(
        choices=status_choices.items(), max_length=15, default=NOT_ARRIVED
    )
    checked_in_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Access Entry"
        verbose_name_plural = "Access Entries"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - {self.event}"

    def clean(self):
        if self.number_of_tickets is not None and self.number_of_tickets < 1:
            raise ValidationError(
                {"number_of_tickets": "Number of tickets must be at least 1."}
            )
        if self.entrance and self.entrance.event_id != self.event_id:
            raise ValidationError(
                {"entrance": "Entrance must belong to the same event."}
            )
        if self.access_level and self.access_level.event_id != self.event_id:
            raise ValidationError(
                {"access_level": "Access level must belong to the same event."}
            )

    @property
    def is_arrived(self):
        return self.status == self.ARRIVED

    @property
    def is_cancelled(self):
        return self.status == self.CANCELLED

    def set_status(self, status):
        self.status = status
        self.checked_in_at = timezone.now() if status == self.ARRIVED else None
        self.save(update_fields=["status", "checked_in_at", "updated_at"])

    @property
    def spaces(self):
        return [se.space for se in self.space_entry.all() if se.space]
