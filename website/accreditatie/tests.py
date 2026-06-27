from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from hospitality.models import Space

from .models import AccessLevel, Event


class EventDetailViewTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            name="Test Event",
            date=date(2026, 6, 27),
            start_time=time(12, 0),
            end_time=time(14, 0),
            location="Main Hall",
        )

    def test_access_level_form_submission_creates_access_level(self):
        response = self.client.post(
            reverse("event_detail", kwargs={"pk": self.event.pk}),
            {
                "submitted_form": "access_level",
                "name": "VIP",
                "color": "#ff0000",
            },
        )

        self.assertRedirects(
            response, reverse("event_detail", kwargs={"pk": self.event.pk})
        )
        self.assertTrue(
            AccessLevel.objects.filter(event=self.event, name="VIP").exists()
        )

    def test_space_form_submission_creates_space(self):
        response = self.client.post(
            reverse("event_detail", kwargs={"pk": self.event.pk}),
            {
                "submitted_form": "space",
                "name": "Backstage",
            },
        )

        self.assertRedirects(
            response, reverse("event_detail", kwargs={"pk": self.event.pk})
        )
        self.assertTrue(
            Space.objects.filter(event=self.event, name="Backstage").exists()
        )
