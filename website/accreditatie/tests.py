from datetime import date, time

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from hospitality.models import HospitalityEntry, Space, SpaceEntry, Types

from .models import AccessEntry, AccessLevel, Entrance, Event


class BaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("crew", password="pw")
        self.client.force_login(self.user)
        self.event = Event.objects.create(
            name="Test Event",
            date=date(2026, 8, 22),
            start_time=time(12, 0),
            end_time=time(23, 0),
            location="Main Hall",
        )
        self.level = AccessLevel.objects.create(
            event=self.event, name="Gold", color="#FFD700"
        )
        self.entrance = Entrance.objects.create(event=self.event, name="Backstage")

    def make_entry(self, **kwargs):
        defaults = {
            "event": self.event,
            "name": "Eva",
            "access_type": AccessEntry.ARTIST,
            "number_of_tickets": 3,
            "access_level": self.level,
            "entrance": self.entrance,
        }
        defaults.update(kwargs)
        return AccessEntry.objects.create(**defaults)


class AuthTests(TestCase):
    def test_pages_require_login(self):
        response = self.client.get(reverse("event_list"))
        self.assertRedirects(response, "/accounts/login/?next=/events/")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Sign in")


class PageRenderTests(BaseTestCase):
    def test_all_pages_render(self):
        entry = self.make_entry()
        Types.objects.create(name="Drink coin", type=Types.COIN, value=1)
        for name, args in [
            ("event_list", []),
            ("event_create", []),
            ("event_detail", [self.event.pk]),
            ("event_edit", [self.event.pk]),
            ("event_setup", [self.event.pk]),
            ("checkin", [self.event.pk]),
            ("event_print", [self.event.pk]),
            ("event_import", [self.event.pk]),
            ("entry_create", [self.event.pk]),
            ("entry_detail", [entry.pk]),
            ("hospitality_list", []),
        ]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200)

    def test_old_url_redirects(self):
        response = self.client.get("/accreditatie/")
        self.assertRedirects(response, reverse("event_list"))


class EventTests(BaseTestCase):
    def test_create_event_goes_to_setup(self):
        response = self.client.post(
            reverse("event_create"),
            {
                "name": "New",
                "location": "Park",
                "date": "2026-09-01",
                "start_time": "10:00",
                "end_time": "18:00",
            },
        )
        event = Event.objects.get(name="New")
        self.assertRedirects(response, reverse("event_setup", args=[event.pk]))

    def test_delete_requires_matching_name(self):
        url = reverse("event_delete", args=[self.event.pk])
        self.client.post(url, {"confirm_name": "wrong"})
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
        self.client.post(url, {"confirm_name": "Test Event"})
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_ticket_stats_ignore_cancelled(self):
        self.make_entry(name="A", number_of_tickets=2, status=AccessEntry.ARRIVED)
        self.make_entry(name="B", number_of_tickets=3)
        self.make_entry(name="C", number_of_tickets=5, status=AccessEntry.CANCELLED)
        stats = self.event.ticket_stats()
        self.assertEqual(stats["tickets"], 5)
        self.assertEqual(stats["arrived"], 2)
        self.assertEqual(stats["expected"], 3)
        self.assertEqual(stats["percent"], 40)
        self.assertEqual(stats["cancelled"], 1)


class SetupTests(BaseTestCase):
    def url(self):
        return reverse("event_setup", args=[self.event.pk])

    def test_add_access_level(self):
        response = self.client.post(
            self.url(),
            {
                "kind": "levels",
                "action": "create",
                "levels-new-name": "VIP",
                "levels-new-color": "#ff0000",
            },
        )
        self.assertRedirects(response, self.url())
        self.assertTrue(AccessLevel.objects.filter(event=self.event, name="VIP").exists())

    def test_add_space_and_entrance(self):
        self.client.post(
            self.url(), {"kind": "spaces", "action": "create", "spaces-new-name": "Dressing room 1"}
        )
        self.client.post(
            self.url(), {"kind": "entrances", "action": "create", "entrances-new-name": "Main gate"}
        )
        self.assertTrue(Space.objects.filter(event=self.event, name="Dressing room 1").exists())
        self.assertTrue(Entrance.objects.filter(event=self.event, name="Main gate").exists())

    def test_duplicate_name_in_same_event_rejected_and_dialog_reopens(self):
        response = self.client.post(
            self.url(),
            {"kind": "levels", "action": "create", "levels-new-name": "gold", "levels-new-color": "#000000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertContains(response, 'data-open-dialog="dlg-levels-new"')

    def test_same_name_allowed_in_other_event(self):
        other = Event.objects.create(
            name="Other", date=date(2026, 9, 1), start_time=time(1), end_time=time(2), location="X"
        )
        self.client.post(
            reverse("event_setup", args=[other.pk]),
            {"kind": "levels", "action": "create", "levels-new-name": "Gold", "levels-new-color": "#000000"},
        )
        self.assertEqual(AccessLevel.objects.filter(name="Gold").count(), 2)

    def test_edit_level(self):
        self.client.post(
            self.url(),
            {
                "kind": "levels",
                "action": "update",
                "item": self.level.pk,
                f"levels-{self.level.pk}-name": "Platinum",
                f"levels-{self.level.pk}-color": "#eeeeee",
            },
        )
        self.level.refresh_from_db()
        self.assertEqual(self.level.name, "Platinum")

    def test_deleting_level_keeps_entries(self):
        entry = self.make_entry()
        self.client.post(self.url(), {"kind": "levels", "action": "delete", "item": self.level.pk})
        entry.refresh_from_db()
        self.assertIsNone(entry.access_level)

    def test_cannot_touch_other_events_items(self):
        other = Event.objects.create(
            name="Other", date=date(2026, 9, 1), start_time=time(1), end_time=time(2), location="X"
        )
        response = self.client.post(
            reverse("event_setup", args=[other.pk]),
            {"kind": "levels", "action": "delete", "item": self.level.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(AccessLevel.objects.filter(pk=self.level.pk).exists())


class EntryTests(BaseTestCase):
    def test_create_entry(self):
        response = self.client.post(
            reverse("entry_create", args=[self.event.pk]),
            {
                "name": "Gotu Jim",
                "access_type": "Artist",
                "number_of_tickets": 4,
                "access_level": self.level.pk,
                "entrance": self.entrance.pk,
            },
        )
        entry = AccessEntry.objects.get(name="Gotu Jim")
        self.assertRedirects(response, reverse("entry_detail", args=[entry.pk]))
        self.assertEqual(entry.event, self.event)
        self.assertEqual(entry.number_of_tickets, 4)

    def test_create_rejects_level_from_other_event(self):
        other = Event.objects.create(
            name="Other", date=date(2026, 9, 1), start_time=time(1), end_time=time(2), location="X"
        )
        foreign = AccessLevel.objects.create(event=other, name="Foreign")
        response = self.client.post(
            reverse("entry_create", args=[self.event.pk]),
            {"name": "X", "access_type": "Crew", "number_of_tickets": 1, "access_level": foreign.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AccessEntry.objects.filter(name="X").exists())

    def test_edit_preselects_current_values(self):
        entry = self.make_entry()
        response = self.client.get(reverse("entry_detail", args=[entry.pk]))
        self.assertContains(response, f'<option value="{self.level.pk}" selected>Gold</option>')
        self.assertContains(response, '<option value="Artist" selected>Artist</option>')

    def test_edit_entry(self):
        entry = self.make_entry()
        self.client.post(
            reverse("entry_detail", args=[entry.pk]),
            {
                "action": "edit",
                "edit-name": "Eva V.",
                "edit-access_type": "Guest",
                "edit-number_of_tickets": 2,
                "edit-access_level": "",
                "edit-entrance": self.entrance.pk,
            },
        )
        entry.refresh_from_db()
        self.assertEqual(entry.name, "Eva V.")
        self.assertEqual(entry.access_type, "Guest")
        self.assertIsNone(entry.access_level)

    def test_invalid_edit_reopens_dialog(self):
        entry = self.make_entry()
        response = self.client.post(
            reverse("entry_detail", args=[entry.pk]),
            {"action": "edit", "edit-name": "", "edit-access_type": "Guest", "edit-number_of_tickets": 0},
        )
        self.assertContains(response, 'data-open-dialog="dlg-edit"')

    def test_check_in_and_undo(self):
        entry = self.make_entry()
        url = reverse("entry_status", args=[entry.pk])
        response = self.client.post(url, {"status": "Arrived", "next": reverse("checkin", args=[self.event.pk])})
        self.assertRedirects(response, reverse("checkin", args=[self.event.pk]))
        entry.refresh_from_db()
        self.assertTrue(entry.is_arrived)
        self.assertIsNotNone(entry.checked_in_at)

        self.client.post(url, {"status": "Not Arrived"})
        entry.refresh_from_db()
        self.assertEqual(entry.status, AccessEntry.NOT_ARRIVED)
        self.assertIsNone(entry.checked_in_at)

    def test_status_ignores_external_next(self):
        entry = self.make_entry()
        response = self.client.post(
            reverse("entry_status", args=[entry.pk]),
            {"status": "Arrived", "next": "https://evil.example/"},
        )
        self.assertRedirects(response, reverse("entry_detail", args=[entry.pk]))

    def test_spaces_assign_and_remove(self):
        entry = self.make_entry()
        space = Space.objects.create(event=self.event, name="Kleedkamer 1")
        url = reverse("entry_detail", args=[entry.pk])
        self.client.post(url, {"action": "space_add", "space": space.pk})
        self.client.post(url, {"action": "space_add", "space": space.pk})
        self.assertEqual(SpaceEntry.objects.filter(entry=entry).count(), 1)
        link = SpaceEntry.objects.get(entry=entry)
        self.client.post(url, {"action": "space_remove", "item": link.pk})
        self.assertFalse(SpaceEntry.objects.filter(entry=entry).exists())

    def test_hospitality_allocate_and_issue(self):
        entry = self.make_entry(number_of_tickets=3)
        coin = Types.objects.create(name="Drink coin", type=Types.COIN, value=1)
        url = reverse("entry_detail", args=[entry.pk])
        self.client.post(url, {"action": "hospitality", "hosp-type": coin.pk, "hosp-amount": 2})
        item = HospitalityEntry.objects.get(entry=entry)
        self.assertEqual(item.total, 6)
        self.client.post(url, {"action": "hospitality_toggle", "item": item.pk})
        item.refresh_from_db()
        self.assertTrue(item.is_issued)

        response = self.client.get(reverse("event_detail", args=[self.event.pk]))
        self.assertContains(response, "<b>6</b> / 6 issued", html=False)

    def test_rider(self):
        entry = self.make_entry()
        url = reverse("entry_detail", args=[entry.pk])
        self.client.post(url, {"action": "rider", "rider-rider": "Still water"})
        self.assertEqual(entry.rider_items.get().rider, "Still water")

    def test_delete_entry(self):
        entry = self.make_entry()
        response = self.client.post(reverse("entry_detail", args=[entry.pk]), {"action": "delete"})
        self.assertRedirects(response, reverse("event_detail", args=[self.event.pk]))
        self.assertFalse(AccessEntry.objects.filter(pk=entry.pk).exists())


class ImportExportTests(BaseTestCase):
    def test_export_csv(self):
        self.make_entry(name="Eva", organisation="Band")
        response = self.client.get(reverse("event_export", args=[self.event.pk]))
        content = response.content.decode("utf-8-sig")
        self.assertIn("name,organisation,type,tickets", content)
        self.assertIn("Eva,Band,Artist,3,Gold,Backstage", content)

    def test_import_csv(self):
        csv_data = (
            "Name;Type;Tickets;Access_level;Entrance\n"
            "Anna;guest;2;gold;Backstage\n"
            "Bob;Wizard;x;Diamond;\n"
            ";;;;\n"
        ).encode()
        response = self.client.post(
            reverse("event_import", args=[self.event.pk]),
            {"file": SimpleUploadedFile("list.csv", csv_data, content_type="text/csv")},
        )
        self.assertRedirects(response, reverse("event_detail", args=[self.event.pk]))
        anna = AccessEntry.objects.get(name="Anna")
        self.assertEqual(anna.access_type, "Guest")
        self.assertEqual(anna.number_of_tickets, 2)
        self.assertEqual(anna.access_level, self.level)
        bob = AccessEntry.objects.get(name="Bob")
        self.assertEqual(bob.access_type, "Crew")
        self.assertEqual(bob.number_of_tickets, 1)
        self.assertIsNone(bob.access_level)
        self.assertEqual(AccessEntry.objects.count(), 2)

    def test_import_without_name_column(self):
        response = self.client.post(
            reverse("event_import", args=[self.event.pk]),
            {"file": SimpleUploadedFile("list.csv", b"foo,bar\n1,2\n")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AccessEntry.objects.exists())
