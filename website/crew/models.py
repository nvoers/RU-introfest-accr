from django.db import models

from accreditation.models import Accreditation, AccreditationType, Company
from core.models import Event, EventDay, new_token


class Team(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#0d9488")
    lead = models.CharField("team lead", max_length=200, blank=True)
    description = models.TextField(
        blank=True, help_text="Shown to volunteers when they sign up."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Shift(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="shifts")
    day = models.ForeignKey(EventDay, on_delete=models.PROTECT, related_name="shifts")
    start = models.TimeField()
    end = models.TimeField()
    location = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    open_for_signup = models.BooleanField(
        default=True, help_text="Volunteers can claim this shift themselves."
    )
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["day__date", "start", "team__name"]

    def __str__(self):
        return f"{self.team} {self.day} {self.start:%H:%M}–{self.end:%H:%M}"

    @property
    def hours(self):
        start = self.start.hour * 60 + self.start.minute
        end = self.end.hour * 60 + self.end.minute
        if end <= start:
            end += 24 * 60
        return round((end - start) / 60, 1)

    def filled(self):
        return self.assignments.count()

    def is_full(self):
        return self.filled() >= self.capacity


class ShiftAssignment(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="assignments")
    person = models.ForeignKey(
        Accreditation, on_delete=models.CASCADE, related_name="shift_assignments"
    )
    self_assigned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["person__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["shift", "person"], name="unique_assignment")
        ]


class VolunteerProfile(models.Model):
    """Extra answers from the public volunteer sign-up form."""

    SHIRT_SIZES = {s: s for s in ["XS", "S", "M", "L", "XL", "XXL"]}

    person = models.OneToOneField(
        Accreditation, on_delete=models.CASCADE, related_name="volunteer"
    )
    preferred_teams = models.ManyToManyField(Team, blank=True)
    available_days = models.ManyToManyField(EventDay, blank=True)
    shirt_size = models.CharField(max_length=4, choices=SHIRT_SIZES.items(), blank=True)
    motivation = models.TextField(blank=True)
    max_hours = models.PositiveIntegerField(null=True, blank=True)


class CrewSettings(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="crew_settings")
    signup_open = models.BooleanField("volunteer sign-up open", default=False)
    signup_token = models.CharField(max_length=40, unique=True, default=new_token)
    accreditation_type = models.ForeignKey(
        AccreditationType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Credential volunteers receive once approved.",
    )
    intro = models.TextField(
        blank=True, help_text="Welcome text at the top of the sign-up form."
    )
    max_shifts_per_person = models.PositiveIntegerField(default=4)

    def volunteers_company(self):
        company, _ = Company.objects.get_or_create(
            event=self.event,
            kind=Company.VOLUNTEERS,
            defaults={"name": "Volunteers", "portal_enabled": False},
        )
        return company

    @classmethod
    def for_event(cls, event):
        settings, _ = cls.objects.get_or_create(event=event)
        return settings
