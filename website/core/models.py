import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def new_token():
    return secrets.token_urlsafe(18)


class Event(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    venue = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("dashboard", args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:70] or "event"
            slug, n = base, 2
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)
        self.sync_days()

    def delete(self, *args, **kwargs):
        """Remove protected dependents first (performances, shifts, people…), then the event."""
        from django.db import transaction

        from accreditation.models import Accreditation
        from artists.models import Artist, HotelRoom, Performance, Transport
        from crew.models import Shift

        with transaction.atomic():
            Performance.objects.filter(artist__event=self).delete()
            Transport.objects.filter(artist__event=self).delete()
            HotelRoom.objects.filter(artist__event=self).delete()
            Artist.objects.filter(event=self).delete()
            Shift.objects.filter(team__event=self).delete()
            Accreditation.objects.filter(event=self).delete()
            return super().delete(*args, **kwargs)

    def sync_days(self):
        """Make sure there is an EventDay for every date in the range."""
        dates = []
        day = self.start_date
        while day <= self.end_date:
            dates.append(day)
            day += timedelta(days=1)
        existing = set(self.days.values_list("date", flat=True))
        EventDay.objects.bulk_create(
            [EventDay(event=self, date=d) for d in dates if d not in existing]
        )
        # Days outside the range are only removed when nothing refers to them.
        for stale in self.days.exclude(date__in=dates):
            try:
                stale.delete()
            except models.ProtectedError:
                pass

    @property
    def is_past(self):
        return self.end_date < timezone.localdate()

    @property
    def is_live(self):
        return self.start_date <= timezone.localdate() <= self.end_date


class EventDay(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="days")
    date = models.DateField()
    label = models.CharField(
        max_length=60, blank=True, help_text="Optional, e.g. “Build-up” or “Show day 1”."
    )

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["event", "date"], name="unique_event_day")
        ]

    def __str__(self):
        return self.short

    @property
    def short(self):
        d = self.date
        return f"{d:%a} {d.day} {d:%b}"

    @property
    def title(self):
        return f"{self.short} · {self.label}" if self.label else self.short


class Activity(models.Model):
    """Lightweight audit trail shown on the dashboard."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    actor_label = models.CharField(max_length=200, blank=True)
    text = models.CharField(max_length=300)
    url = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activity"

    def __str__(self):
        return self.text

    @property
    def who(self):
        if self.actor:
            return self.actor.get_full_name() or self.actor.get_username()
        return self.actor_label or "System"


def log(event, text, user=None, label="", url=""):
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    Activity.objects.create(
        event=event, actor=user, actor_label=label, text=text[:300], url=url
    )
