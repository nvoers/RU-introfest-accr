from django.db import models
from django.urls import reverse

from accreditation.models import Company
from core.models import Event, EventDay


class Stage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#7c3aed")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Artist(models.Model):
    NOT_STARTED, IN_PROGRESS, SUBMITTED, COMPLETE = (
        "not_started",
        "in_progress",
        "submitted",
        "complete",
    )
    ADVANCING = {
        NOT_STARTED: "Not started",
        IN_PROGRESS: "In progress",
        SUBMITTED: "Submitted",
        COMPLETE: "Complete",
    }

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="artists")
    name = models.CharField(max_length=200)
    # The artist's party is requested through this company's portal.
    company = models.OneToOneField(
        Company, on_delete=models.PROTECT, related_name="artist"
    )
    agent = models.CharField(max_length=200, blank=True)
    advancing_status = models.CharField(
        max_length=20, choices=ADVANCING.items(), default=NOT_STARTED
    )

    # Advancing sheet – filled in by the artist's tour manager or by the organiser.
    arrival = models.TextField(
        "arrival & departure", blank=True, help_text="When and how they arrive and leave."
    )
    technical_rider = models.TextField(blank=True)
    hospitality_rider = models.TextField(blank=True)
    rider_file = models.FileField(upload_to="riders/", blank=True)
    dressing_room = models.CharField(max_length=200, blank=True)
    party_size = models.PositiveIntegerField(
        "expected party size", null=True, blank=True
    )
    internal_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("artist_detail", args=[self.event.slug, self.pk])

    @property
    def first_performance(self):
        return self.performances.select_related("stage", "day").first()


class Performance(models.Model):
    artist = models.ForeignKey(
        Artist, on_delete=models.CASCADE, related_name="performances"
    )
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="performances")
    day = models.ForeignKey(EventDay, on_delete=models.PROTECT, related_name="performances")
    start = models.TimeField()
    end = models.TimeField()
    changeover_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["day__date", "start"]

    def __str__(self):
        return f"{self.artist} @ {self.stage} {self.day} {self.start:%H:%M}"

    @property
    def start_minutes(self):
        return self.start.hour * 60 + self.start.minute

    @property
    def end_minutes(self):
        end = self.end.hour * 60 + self.end.minute
        return end if end > self.start_minutes else end + 24 * 60  # past midnight


class Request(models.Model):
    """Base for logistic requests that the organiser confirms."""

    REQUESTED, CONFIRMED, DECLINED = "requested", "confirmed", "declined"
    STATUSES = {REQUESTED: "Requested", CONFIRMED: "Confirmed", DECLINED: "Declined"}

    status = models.CharField(max_length=20, choices=STATUSES.items(), default=REQUESTED)
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        abstract = True


class Transport(Request):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="transports")
    day = models.ForeignKey(EventDay, on_delete=models.PROTECT)
    time = models.TimeField()
    pickup = models.CharField("from", max_length=200)
    dropoff = models.CharField("to", max_length=200)
    passengers = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["day__date", "time"]


class HotelRoom(Request):
    SINGLE, DOUBLE, TWIN = "single", "double", "twin"
    ROOM_TYPES = {SINGLE: "Single", DOUBLE: "Double", TWIN: "Twin"}

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="rooms")
    hotel = models.CharField(max_length=200, blank=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES.items(), default=SINGLE)
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.CharField("guest names", max_length=300)

    class Meta:
        ordering = ["check_in"]

    @property
    def nights(self):
        return max((self.check_out - self.check_in).days, 0)
