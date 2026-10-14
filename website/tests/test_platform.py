from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accreditation import services
from accreditation.models import (
    Accreditation,
    AccreditationType,
    Company,
    Contingent,
    Item,
    Scan,
    TypeItem,
    Zone,
)
from artists.models import Artist, Performance, Stage
from core.models import Event
from crew.models import CrewSettings, Shift, ShiftAssignment, Team


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("org", password="pw", is_staff=True)
        self.client.force_login(self.user)
        today = timezone.localdate()
        self.event = Event.objects.create(name="Fest", start_date=today, end_date=today + timedelta(days=1))
        self.day1, self.day2 = self.event.days.all()
        self.backstage = Zone.objects.create(event=self.event, name="Backstage")
        self.vip = Zone.objects.create(event=self.event, name="VIP")
        self.wristband = Item.objects.create(event=self.event, name="Wristband", kind="wristband")
        self.crew = AccreditationType.objects.create(event=self.event, name="Crew")
        self.crew.zones.add(self.backstage)
        TypeItem.objects.create(type=self.crew, item=self.wristband, quantity=1)
        self.company = Company.objects.create(event=self.event, name="Sound BV", contact_email="tm@sound.test")
        Contingent.objects.create(company=self.company, type=self.crew, quota=2)

    def url(self, name, *args):
        return reverse(name, args=[self.event.slug, *args])

    def person(self, **kw):
        data = dict(event=self.event, type=self.crew, first_name="Eva", last_name="V", email="eva@test.nl")
        data.update(kw)
        return Accreditation.objects.create(**data)


class EventTests(Base):
    def test_days_follow_date_range(self):
        self.assertEqual(self.event.days.count(), 2)
        self.event.end_date = self.event.start_date + timedelta(days=3)
        self.event.save()
        self.assertEqual(self.event.days.count(), 4)
        self.event.end_date = self.event.start_date
        self.event.save()
        self.assertEqual(self.event.days.count(), 1)

    def test_login_required_but_portal_public(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url("dashboard")).status_code, 302)
        self.assertEqual(self.client.get(reverse("portal_home", args=[self.company.token])).status_code, 200)

    def test_all_organiser_pages_render_with_demo_data(self):
        call_command("seed_demo", name="Demo", stdout=open("/dev/null", "w"))
        event = Event.objects.get(name="Demo")
        acc = event.accreditations.filter(status="approved").first()
        artist = event.artists.first()
        company = event.companies.first()
        pages = ["dashboard", "people", "approvals", "companies", "scanner", "artist_list", "timetable",
                 "logistics", "shifts", "roster", "volunteers", "teams", "zones", "types", "items",
                 "stages", "event_settings", "person_create"]
        for name in pages:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[event.slug])).status_code, 200)
        for name, pk in [("person_detail", acc.pk), ("person_edit", acc.pk), ("artist_detail", artist.pk),
                         ("company_detail", company.pk)]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[event.slug, pk])).status_code, 200)
        for url in [reverse("event_list"), reverse("ticket", args=[acc.token]),
                    reverse("portal_home", args=[artist.company.token]) + "?tab=advancing",
                    reverse("portal_home", args=[artist.company.token]) + "?tab=logistics",
                    reverse("volunteer_signup", args=[event.crew_settings.signup_token])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse("people_export", args=[event.slug])).status_code, 200)

        # Deleting a fully populated event works (protected relations are removed first).
        response = self.client.post(reverse("event_delete", args=[event.slug]), {"confirm": "Demo"})
        self.assertRedirects(response, reverse("event_list"))
        self.assertFalse(Event.objects.filter(name="Demo").exists())

    def test_seed_refuses_to_overwrite(self):
        from django.core.management.base import CommandError

        call_command("seed_demo", name="Fest2", stdout=open("/dev/null", "w"))
        with self.assertRaises(CommandError):
            call_command("seed_demo", name="Fest2", stdout=open("/dev/null", "w"))


class SetupTests(Base):
    def test_type_form_sets_default_items(self):
        response = self.client.post(self.url("types"), {
            "f-new-name": "Guest", "f-new-color": "#ffcc00", "f-new-zones": [self.vip.pk],
            "f-new-order": 0, f"f-new-item_{self.wristband.pk}": 2,
        })
        self.assertEqual(response.status_code, 302)
        guest = AccreditationType.objects.get(name="Guest")
        self.assertEqual(list(guest.zones.all()), [self.vip])
        self.assertEqual(guest.default_items.get().quantity, 2)

    def test_type_in_use_cannot_be_deleted(self):
        self.person()
        self.client.post(self.url("types"), {"action": "delete", "item": self.crew.pk})
        self.assertTrue(AccreditationType.objects.filter(pk=self.crew.pk).exists())

    def test_zone_from_other_event_is_404(self):
        other = Event.objects.create(name="Other", start_date=date(2030, 1, 1), end_date=date(2030, 1, 1))
        response = self.client.post(reverse("zones", args=[other.slug]), {"action": "delete", "item": self.vip.pk})
        self.assertEqual(response.status_code, 404)


class PeopleTests(Base):
    def test_organiser_adds_person_approved_with_items_and_email(self):
        response = self.client.post(self.url("person_create"), {
            "first_name": "Bram", "last_name": "Bos", "type": self.crew.pk, "email": "bram@test.nl",
            "send_ticket": "on",
        })
        acc = Accreditation.objects.get(first_name="Bram")
        self.assertRedirects(response, acc.get_absolute_url())
        self.assertEqual(acc.status, Accreditation.APPROVED)
        self.assertEqual(acc.items.get().item, self.wristband)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(acc.ticket_url(), mail.outbox[0].body)

    def test_bulk_approve_and_reject(self):
        a = self.person(status=Accreditation.PENDING)
        b = self.person(first_name="Tim", status=Accreditation.PENDING)
        self.client.post(self.url("approvals"), {"ids": [a.pk], "bulk": "approve"})
        self.client.post(self.url("approvals"), {"ids": [b.pk], "bulk": "reject", "reason": "Full"})
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, "approved")
        self.assertEqual(b.status, "rejected")
        self.assertEqual(b.rejection_reason, "Full")
        self.assertEqual(a.decided_by, self.user)

    def test_single_approve_button(self):
        a = self.person(status=Accreditation.PENDING)
        self.client.post(self.url("approvals"), {"single": a.pk})
        a.refresh_from_db()
        self.assertTrue(a.is_approved)

    def test_people_filters(self):
        self.person(first_name="Anna", status="approved")
        self.person(first_name="Bob", status="pending")
        response = self.client.get(self.url("people") + "?status=pending")
        self.assertContains(response, "Bob")
        self.assertNotContains(response, "Anna V")
        response = self.client.get(self.url("people") + "?q=ann")
        self.assertContains(response, "Anna")


class PortalTests(Base):
    def portal(self, **params):
        return reverse("portal_home", args=[self.company.token])

    def add(self, first):
        return self.client.post(self.portal(), {
            "action": "person", "p-first_name": first, "p-last_name": "X", "p-type": self.crew.pk,
            "p-email": f"{first}@x.nl",
        })

    def test_partner_flow_draft_submit_approve(self):
        self.client.logout()
        self.add("Lotte")
        acc = Accreditation.objects.get(first_name="Lotte")
        self.assertEqual(acc.status, "draft")
        self.assertEqual(acc.company, self.company)
        self.client.post(self.portal(), {"action": "submit"})
        acc.refresh_from_db()
        self.assertEqual(acc.status, "pending")

        self.client.force_login(self.user)
        self.client.post(self.url("approvals"), {"ids": [acc.pk], "bulk": "approve"})
        acc.refresh_from_db()
        self.assertTrue(acc.is_approved)
        self.assertEqual(len(mail.outbox), 1)

    def test_contingent_is_enforced(self):
        self.add("A")
        self.add("B")
        response = self.add("C")
        self.assertContains(response, "contingent")
        self.assertEqual(self.company.accreditations.count(), 2)

    def test_no_approval_needed_type(self):
        self.crew.requires_approval = False
        self.crew.save()
        self.add("Auto")
        self.client.post(self.portal(), {"action": "submit"})
        self.assertTrue(Accreditation.objects.get(first_name="Auto").is_approved)

    def test_closed_portal_404(self):
        self.company.portal_enabled = False
        self.company.save()
        self.assertEqual(self.client.get(self.portal()).status_code, 404)

    def test_partner_cannot_touch_other_company(self):
        other = Company.objects.create(event=self.event, name="Other")
        acc = self.person(company=other, status="draft")
        response = self.client.post(self.portal(), {"action": "delete", "item": acc.pk})
        self.assertEqual(response.status_code, 404)


class ScanTests(Base):
    def test_scan_rules(self):
        acc = self.person(status=Accreditation.APPROVED)
        r = services.process_scan(self.event, acc.token)
        self.assertEqual(r["result"], Scan.OK)
        self.assertTrue(r["first_time"])
        r = services.process_scan(self.event, acc.token)
        self.assertEqual(r["result"], Scan.WARNING)  # already inside
        self.assertEqual(services.process_scan(self.event, acc.token, self.backstage)["result"], Scan.OK)
        self.assertEqual(services.process_scan(self.event, acc.token, self.vip)["result"], Scan.DENIED)
        self.assertEqual(services.process_scan(self.event, "nope")["result"], Scan.DENIED)
        r = services.process_scan(self.event, acc.token, direction=Scan.OUT)
        acc.refresh_from_db()
        self.assertFalse(acc.is_inside)

    def test_wrong_day_and_status_denied(self):
        acc = self.person(status=Accreditation.APPROVED)
        acc.days.set([self.day2])
        self.assertEqual(services.process_scan(self.event, acc.token)["message"], "Not valid today")
        pending = self.person(first_name="P", status=Accreditation.PENDING)
        self.assertEqual(services.process_scan(self.event, pending.token)["result"], Scan.DENIED)

    def test_scan_api_and_ticket_url_code(self):
        acc = self.person(status=Accreditation.APPROVED)
        response = self.client.post(self.url("scan_api"), {"code": f"https://x/t/{acc.token}/"},
                                    content_type="application/json")
        self.assertEqual(response.json()["name"], "Eva V")

    def test_other_event_ticket_is_unknown(self):
        other = Event.objects.create(name="Other", start_date=date(2030, 1, 1), end_date=date(2030, 1, 1))
        acc = self.person(status=Accreditation.APPROVED)
        self.assertEqual(services.process_scan(other, acc.token)["message"], "Unknown code")


class ArtistTests(Base):
    def setUp(self):
        super().setUp()
        self.stage = Stage.objects.create(event=self.event, name="Main")
        self.client.post(reverse("artist_list", args=[self.event.slug]),
                         {"f-new-name": "Goldband", "f-new-contact_email": "tm@gold.test"})
        self.artist = Artist.objects.get(name="Goldband")

    def test_artist_gets_company(self):
        self.assertEqual(self.artist.company.kind, Company.ARTIST)
        self.assertEqual(self.artist.company.contact_email, "tm@gold.test")

    def test_performance_overlap_rejected(self):
        url = reverse("artist_detail", args=[self.event.slug, self.artist.pk])
        data = {"action": "performance", "performance-stage": self.stage.pk, "performance-day": self.day1.pk,
                "performance-start": "20:00", "performance-end": "21:00", "performance-changeover_minutes": 0}
        self.client.post(url, data)
        response = self.client.post(url, {**data, "performance-start": "20:30", "performance-end": "21:30"})
        self.assertContains(response, "Overlaps")
        self.assertEqual(Performance.objects.count(), 1)

    def test_portal_advancing_submit(self):
        self.client.logout()
        url = reverse("portal_home", args=[self.artist.company.token]) + "?tab=advancing"
        self.client.post(url, {"action": "advancing", "adv-arrival": "15:00 by bus", "submit": "1"})
        self.artist.refresh_from_db()
        self.assertEqual(self.artist.advancing_status, Artist.SUBMITTED)
        self.assertEqual(self.artist.arrival, "15:00 by bus")

    def test_portal_transport_request(self):
        self.client.logout()
        url = reverse("portal_home", args=[self.artist.company.token]) + "?tab=logistics"
        self.client.post(url, {"action": "transport", "transport-day": self.day1.pk, "transport-time": "14:00",
                               "transport-pickup": "Station", "transport-dropoff": "Gate", "transport-passengers": 4})
        self.assertEqual(self.artist.transports.get().status, "requested")

    def test_timetable_handles_past_midnight(self):
        Performance.objects.create(artist=self.artist, stage=self.stage, day=self.day1, start=time(23), end=time(1))
        response = self.client.get(reverse("timetable", args=[self.event.slug]))
        self.assertContains(response, "Goldband")


class CrewTests(Base):
    def setUp(self):
        super().setUp()
        self.team = Team.objects.create(event=self.event, name="Bar")
        self.shift = Shift.objects.create(team=self.team, day=self.day1, start=time(12), end=time(16), capacity=1)
        self.settings = CrewSettings.for_event(self.event)
        self.settings.signup_open = True
        self.settings.accreditation_type = self.crew
        self.settings.save()

    def signup(self, email="v@x.nl"):
        return self.client.post(reverse("volunteer_signup", args=[self.settings.signup_token]), {
            "first_name": "Vera", "last_name": "V", "email": email, "phone": "06",
            "preferred_teams": [self.team.pk], "available_days": [self.day1.pk],
        })

    def test_volunteer_signup_and_claim_shift(self):
        self.client.logout()
        self.signup()
        acc = Accreditation.objects.get(first_name="Vera")
        self.assertEqual(acc.status, "pending")
        self.assertEqual(acc.company.kind, Company.VOLUNTEERS)
        self.assertEqual(self.signup().status_code, 200)  # duplicate e-mail
        services.approve(acc)
        ticket = reverse("ticket", args=[acc.token])
        self.assertContains(self.client.get(ticket), "Sign up")
        self.client.post(ticket, {"action": "claim", "shift": self.shift.pk})
        self.assertTrue(ShiftAssignment.objects.filter(shift=self.shift, person=acc).exists())

    def test_full_and_overlapping_shifts_refused(self):
        a = self.person(status="approved")
        b = self.person(first_name="B", status="approved")
        ShiftAssignment.objects.create(shift=self.shift, person=a)
        self.client.post(reverse("ticket", args=[b.token]), {"action": "claim", "shift": self.shift.pk})
        self.assertEqual(self.shift.assignments.count(), 1)
        overlap = Shift.objects.create(team=self.team, day=self.day1, start=time(15), end=time(18), capacity=5)
        self.client.post(reverse("ticket", args=[a.token]), {"action": "claim", "shift": overlap.pk})
        self.assertFalse(overlap.assignments.exists())

    def test_closed_signup(self):
        self.settings.signup_open = False
        self.settings.save()
        response = self.client.get(reverse("volunteer_signup", args=[self.settings.signup_token]))
        self.assertContains(response, "closed")

    def test_organiser_assigns_shift(self):
        acc = self.person(status="approved")
        self.client.post(self.url("shifts"), {"action": "assign", "item": self.shift.pk, "person": acc.pk})
        self.assertTrue(self.shift.assignments.filter(person=acc).exists())
