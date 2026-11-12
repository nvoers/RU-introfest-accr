from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accreditation.models import Accreditation, AccreditationType
from core.models import Event, Membership


class RoleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", name="Demo", stdout=open("/dev/null", "w"))
        cls.event = Event.objects.get(name="Demo")
        cls.other = Event.objects.create(name="Other", start_date=timezone.localdate(),
                                         end_date=timezone.localdate() + timedelta(days=1))
        cls.person = cls.event.accreditations.filter(status="approved").first()
        cls.users = {}
        for role in ["manager", "accreditation", "artists", "crew", "checkin", "viewer"]:
            user = User.objects.create_user(role, email=f"{role}@x.nl", password="pw")
            Membership.objects.create(user=user, event=cls.event, role=role)
            cls.users[role] = user
        cls.outsider = User.objects.create_user("outsider", password="pw")

    def as_(self, role):
        self.client.force_login(self.users[role] if role != "outsider" else self.outsider)

    def url(self, name, *args):
        return reverse(name, args=[self.event.slug, *args])

    def status(self, role, name, *args, method="get", data=None):
        self.as_(role)
        call = getattr(self.client, method)
        return call(self.url(name, *args), data or {}).status_code

    def test_page_access_matrix(self):
        # role -> pages they may open (others must be 403)
        pages = ["people", "approvals", "companies", "scanner", "artist_list", "timetable",
                 "shifts", "roster", "zones", "types", "event_settings", "team"]
        allowed = {
            "manager": set(pages),
            "accreditation": {"people", "approvals", "companies", "scanner", "artist_list",
                              "timetable", "shifts", "roster", "zones", "types"},
            "artists": {"people", "approvals", "companies", "artist_list", "timetable", "zones", "types"},
            "crew": {"people", "approvals", "companies", "shifts", "roster", "zones", "types"},
            "checkin": {"scanner"},
            "viewer": {"people", "approvals", "companies", "artist_list", "timetable", "shifts",
                       "roster", "zones", "types"},
        }
        for role, ok in allowed.items():
            for page in pages:
                with self.subTest(role=role, page=page):
                    expected = 200 if page in ok else 403
                    self.assertEqual(self.status(role, page), expected)

    def test_view_only_roles_cannot_change(self):
        for role in ["viewer", "artists", "crew"]:
            with self.subTest(role=role):
                code = self.status(role, "person_detail", self.person.pk, method="post",
                                   data={"action": "cancel"})
                self.assertEqual(code, 403)
                self.assertEqual(self.status(role, "person_create"), 403)
        self.person.refresh_from_db()
        self.assertEqual(self.person.status, "approved")

    def test_readonly_page_hides_forms(self):
        self.as_("viewer")
        response = self.client.get(self.url("person_detail", self.person.pk))
        self.assertContains(response, 'class="content readonly"')
        self.as_("accreditation")
        response = self.client.get(self.url("person_detail", self.person.pk))
        self.assertNotContains(response, 'class="content readonly"')

    def test_editor_roles_can_change_their_area(self):
        self.assertEqual(self.status("accreditation", "person_detail", self.person.pk, method="post",
                                     data={"action": "send"}), 302)
        self.assertEqual(self.status("crew", "teams", method="post",
                                     data={"f-new-name": "Stage crew", "f-new-color": "#000000"}), 302)
        self.assertEqual(self.status("artists", "stages", method="post",
                                     data={"f-new-name": "X", "f-new-color": "#000000", "f-new-order": 0}), 403)

    def test_checkin_staff_scan_and_land_on_scanner(self):
        self.as_("checkin")
        response = self.client.post(self.url("scan_api"), {"code": self.person.token},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(self.client.get(reverse("event_list")), self.url("scanner"),
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.get(self.url("dashboard")), self.url("scanner"),
                             fetch_redirect_response=False)
        self.assertEqual(self.status("checkin", "person_detail", self.person.pk), 403)

    def test_outsiders_and_other_events(self):
        self.assertEqual(self.status("outsider", "dashboard"), 403)
        self.as_("manager")
        response = self.client.get(reverse("event_list"))
        self.assertContains(response, "Demo")
        self.assertNotContains(response, "Other")
        self.assertEqual(self.client.get(reverse("dashboard", args=[self.other.slug])).status_code, 403)

    def test_only_admins_create_events(self):
        self.as_("manager")
        self.assertEqual(self.client.get(reverse("event_create")).status_code, 403)
        staff = User.objects.create_user("staff", password="pw", is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse("event_create"), {"name": "New fest", "start_date": "2030-01-01",
                                                   "end_date": "2030-01-02"})
        event = Event.objects.get(name="New fest")
        self.assertEqual(Membership.objects.get(event=event, user=staff).role, "manager")

    def test_invite_new_member_and_set_password(self):
        self.as_("manager")
        self.client.post(self.url("team"), {"action": "invite", "f-new-email": "New@Crew.nl",
                                            "f-new-first_name": "Nina", "f-new-role": "crew"})
        user = User.objects.get(email="new@crew.nl")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(Membership.objects.get(user=user, event=self.event).role, "crew")
        link = [l for l in mail.outbox[-1].body.split() if "/accounts/reset/" in l][0]
        path = link.split("8000", 1)[1] if "8000" in link else link
        self.client.logout()
        response = self.client.get(path, follow=True)
        response = self.client.post(response.redirect_chain[-1][0],
                                    {"new_password1": "a-Strong-pass-42", "new_password2": "a-Strong-pass-42"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.login(username="new@crew.nl", password="a-Strong-pass-42"))

    def test_existing_user_invite_updates_role(self):
        self.as_("manager")
        self.client.post(self.url("team"), {"action": "invite", "f-new-email": "viewer@x.nl", "f-new-role": "artists"})
        self.assertEqual(Membership.objects.get(user=self.users["viewer"], event=self.event).role, "artists")

    def test_last_manager_is_protected(self):
        self.as_("manager")
        m = Membership.objects.get(user=self.users["manager"], event=self.event)
        self.client.post(self.url("team"), {"action": "remove", "item": m.pk})
        self.client.post(self.url("team"), {"action": "role", "item": m.pk, "role": "viewer"})
        m.refresh_from_db()
        self.assertEqual(m.role, "manager")

    def test_non_manager_cannot_manage_team(self):
        self.assertEqual(self.status("accreditation", "team", method="post",
                                     data={"action": "invite", "f-new-email": "x@x.nl", "f-new-role": "manager"}), 403)

    def test_email_login(self):
        self.assertTrue(self.client.login(username="CREW@x.nl", password="pw"))

    def test_sidebar_follows_role(self):
        self.as_("crew")
        response = self.client.get(self.url("shifts"))
        self.assertContains(response, self.url("roster"))
        self.assertNotContains(response, self.url("scanner"))
        self.assertNotContains(response, self.url("team"))


class ConsoleMailTests(TestCase):
    def test_links_are_printed_unwrapped(self):
        import io

        from django.core.mail import EmailMessage

        from core.mail import EmailBackend

        link = "http://127.0.0.1:8000/accounts/reset/NQ/" + "a" * 60 + "/"
        stream = io.StringIO()
        EmailBackend(stream=stream).send_messages(
            [EmailMessage("Invite", f"Choose a password:\n{link}\n", "x@x.nl", ["y@y.nl"])]
        )
        self.assertIn(link, stream.getvalue())
