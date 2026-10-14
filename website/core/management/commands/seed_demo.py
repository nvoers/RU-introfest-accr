"""Create a demo event with realistic data: `python manage.py seed_demo`."""

import random
from datetime import time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
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
from artists.models import Artist, HotelRoom, Performance, Stage, Transport
from core.models import Event, log
from crew.models import CrewSettings, Shift, ShiftAssignment, Team, VolunteerProfile

FIRST = ["Sanne", "Daan", "Lotte", "Bram", "Noor", "Jesse", "Eva", "Thijs", "Fleur", "Milan",
         "Sophie", "Luuk", "Julia", "Sem", "Lisa", "Finn", "Anna", "Ruben", "Yara", "Koen",
         "Mila", "Timo", "Iris", "Gijs", "Femke", "Joris", "Esmee", "Niels", "Zoë", "Stijn"]
LAST = ["de Vries", "Jansen", "Bakker", "Visser", "Smit", "Meijer", "de Boer", "Mulder",
        "de Groot", "Bos", "Vos", "Peters", "Hendriks", "van Leeuwen", "Dekker", "Brouwer"]


class Command(BaseCommand):
    help = "Create a demo event with zones, credentials, companies, artists and crew."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Introfestival Demo")
        parser.add_argument(
            "--replace", action="store_true", help="Delete an existing event with this name first."
        )

    def handle(self, *args, name, replace=False, **options):
        if Event.objects.filter(name=name).exists() and not replace:
            raise CommandError(
                f"An event named “{name}” already exists. Use --replace to delete and recreate it, "
                "or --name to pick another name."
            )
        rnd = random.Random(42)
        person = lambda: (rnd.choice(FIRST), rnd.choice(LAST))  # noqa: E731
        today = timezone.localdate()
        for existing in Event.objects.filter(name=name):
            existing.delete()
        event = Event.objects.create(
            name=name,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=1),
            venue="Park Brakkenstein, Nijmegen",
            description="Demo data created by seed_demo.",
        )
        d1, d2, d3 = event.days.all()
        d1.label, d2.label, d3.label = "Build-up", "Show day", "Break-down"
        for d in (d1, d2, d3):
            d.save()

        z = {
            n: Zone.objects.create(event=event, name=n, code=c, color=col, order=i)
            for i, (n, c, col) in enumerate(
                [("Terrain", "T", "#22c55e"), ("Backstage", "BS", "#f59e0b"),
                 ("Stage", "ST", "#ef4444"), ("Production", "PR", "#3b82f6"), ("VIP", "VIP", "#a855f7")]
            )
        }
        it = {
            n: Item.objects.create(event=event, name=n, kind=k)
            for n, k in [("Crew wristband", "wristband"), ("Artist wristband", "wristband"),
                         ("Guest wristband", "wristband"), ("Drink tokens", "voucher"),
                         ("Meal voucher", "voucher"), ("Parking P2", "parking"), ("Crew T-shirt", "merch")]
        }
        it["Payment card"] = Item.objects.create(
            event=event, name="Payment card", kind=Item.PAYMENT_CARD, default_amount=Decimal("10.00"),
            description="Cashless card for food & drinks on the terrain",
        )

        def ctype(name, color, zones, items, approval=True, order=0):
            t = AccreditationType.objects.create(
                event=event, name=name, color=color, requires_approval=approval, order=order
            )
            t.zones.set([z[n] for n in zones])
            for item, qty in items:
                if it[item].is_payment_card:
                    TypeItem.objects.create(type=t, item=it[item], quantity=1, amount=Decimal(str(qty)))
                else:
                    TypeItem.objects.create(type=t, item=it[item], quantity=qty)
            return t

        artist_t = ctype("Artist", "#e0457b", ["Terrain", "Backstage", "Stage"], [("Artist wristband", 1), ("Meal voucher", 1), ("Payment card", 25)], order=1)
        crew_t = ctype("Crew", "#111827", ["Terrain", "Backstage", "Stage", "Production"], [("Crew wristband", 1), ("Meal voucher", 1), ("Crew T-shirt", 1), ("Payment card", 15)], order=2)
        prod_t = ctype("Production", "#2563eb", list(z), [("Crew wristband", 1), ("Parking P2", 1)], order=3)
        guest_t = ctype("Guest", "#facc15", ["Terrain", "VIP"], [("Guest wristband", 1), ("Payment card", 20)], order=4)
        press_t = ctype("Press", "#14b8a6", ["Terrain", "Backstage"], [("Guest wristband", 1)], order=5)
        supplier_t = ctype("Supplier", "#78716c", ["Terrain", "Production"], [("Parking P2", 1)], approval=False, order=6)
        vol_t = ctype("Volunteer", "#16a34a", ["Terrain"], [("Crew wristband", 1), ("Crew T-shirt", 1)], order=7)
        # What volunteers earn per shift, depending on where they work (see Teams/Shifts).
        bar_shift = ctype("Bar shift", "#f59e0b", [], [("Meal voucher", 1)], order=10)
        disco_shift = ctype("Silent disco shift", "#a855f7", ["Backstage"], [("Payment card", 12.5)], order=11)
        disco_dinner = ctype("Dinner shift extra", "#7c3aed", [], [("Payment card", 12.5)], order=12)

        def add(company, type_, status="approved", role="", days=None):
            first, last = person()
            acc = Accreditation.objects.create(
                event=event, company=company, type=type_, first_name=first, last_name=last,
                email=f"{first.lower()}.{last.replace(' ', '').lower()}@example.com",
                role=role, status=status,
            )
            if days:
                acc.days.set(days)
            if status == "pending":
                acc.set_status("pending")
            if status == "approved":
                acc.apply_default_items()
            return acc

        internal = Company.objects.create(event=event, name="Festival organisation", kind="internal", portal_enabled=False)
        for role in ["Festival director", "Head of production", "Site manager", "Stage manager", "Artist liaison", "Safety officer"]:
            add(internal, prod_t, role=role)

        partners = [
            ("Stage Sound & Light", "supplier", {crew_t: 8}, 6, crew_t, "Technician"),
            ("Bar & Catering Co.", "supplier", {supplier_t: 10, crew_t: 4}, 7, supplier_t, "Bar staff"),
            ("Radio Gelderland", "press", {press_t: 4}, 3, press_t, "Reporter"),
            ("Radboud University", "partner", {guest_t: 12}, 9, guest_t, "Guest"),
            ("Security Plus", "supplier", {crew_t: 12}, 10, crew_t, "Steward"),
        ]
        for name_, kind, quota, n, type_, role in partners:
            c = Company.objects.create(event=event, name=name_, kind=kind, contact_name=" ".join(person()),
                                       contact_email=f"info@{name_.split()[0].lower()}.example.com")
            for t, q in quota.items():
                Contingent.objects.create(company=c, type=t, quota=q)
            for i in range(n):
                status = "pending" if i >= n - 2 and kind != "supplier" else "approved"
                if name_ == "Security Plus" and i >= n - 3:
                    status = "pending"
                add(c, type_, status=status, role=role, days=[d2] if type_ == guest_t else None)

        stages = [Stage.objects.create(event=event, name=n, color=c, order=i)
                  for i, (n, c) in enumerate([("Main stage", "#e0457b"), ("The Tent", "#6d5dfc"), ("Club", "#0d9488")])]
        lineup = [
            ("Froukje", 0, 21, 0, 22, 15, "complete"), ("Goldband", 0, 19, 30, 20, 30, "submitted"),
            ("S10", 0, 18, 0, 18, 50, "in_progress"), ("Pip Blom", 1, 20, 0, 21, 0, "complete"),
            ("Kensington", 0, 22, 45, 0, 15, "submitted"), ("Joost", 1, 22, 0, 23, 0, "not_started"),
            ("DJ Kaas", 2, 23, 0, 1, 0, "in_progress"), ("Merol", 1, 18, 30, 19, 20, "not_started"),
            ("Eefje de Visser", 2, 21, 0, 22, 0, "complete"),
        ]
        for name_, s, h1, m1, h2, m2, adv in lineup:
            c = Company.objects.create(event=event, name=name_, kind="artist", contact_name=" ".join(person()),
                                       contact_email=f"tm@{name_.split()[0].lower()}.example.com")
            Contingent.objects.create(company=c, type=artist_t, quota=6)
            Contingent.objects.create(company=c, type=guest_t, quota=4)
            a = Artist.objects.create(
                event=event, name=name_, company=c, agent=rnd.choice(["Mojo", "Friendly Fire", "Paperclip"]),
                advancing_status=adv, party_size=rnd.randint(3, 8), dressing_room=f"Dressing room {rnd.randint(1, 6)}",
                arrival="Nightliner arrives at the backstage gate around 15:00." if adv != "not_started" else "",
                technical_rider="Own FOH engineer. 2x wedges, IEM for vocals." if adv in ("submitted", "complete") else "",
                hospitality_rider="Still water, fruit, hot meal for 6 (1 vegan)." if adv in ("submitted", "complete") else "",
            )
            Performance.objects.create(artist=a, stage=stages[s], day=d2, start=time(h1, m1), end=time(h2, m2))
            for i in range(rnd.randint(2, 4)):
                add(c, artist_t, status="approved" if adv != "not_started" else "draft",
                    role=["Musician", "Tour manager", "FOH engineer", "Backliner"][i])
            if adv in ("submitted", "complete"):
                Transport.objects.create(artist=a, day=d2, time=time(max(h1 - 4, 10), 0), pickup="Nijmegen Centraal",
                                         dropoff="Backstage gate", passengers=rnd.randint(2, 6),
                                         status="confirmed" if adv == "complete" else "requested")
                HotelRoom.objects.create(artist=a, room_type="double", check_in=d2.date, check_out=d3.date,
                                         guests="Band", hotel="Hotel Nijmegen" if adv == "complete" else "",
                                         status="confirmed" if adv == "complete" else "requested")

        teams = [Team.objects.create(event=event, name=n, color=c, lead=" ".join(person()), description=d)
                 for n, c, d in [("Bar", "#f59e0b", "Pour drinks and keep the bars running."),
                                 ("Entrance", "#3b82f6", "Scan tickets and welcome visitors."),
                                 ("Clean-up", "#16a34a", "Keep the terrain clean."),
                                 ("Silent disco", "#a855f7", "Hand out and collect headphones.")]]
        teams[0].shift_credential = bar_shift
        teams[0].save()
        teams[3].shift_credential = disco_shift
        teams[3].save()
        settings = CrewSettings.for_event(event)
        settings.signup_open = True
        settings.accreditation_type = vol_t
        settings.intro = "Help make the festival happen! Volunteers get a free shirt, meals and a ticket for the after-party."
        settings.save()
        vol_company = settings.volunteers_company()
        shifts = []
        for team in teams:
            for day in (d1, d2, d3) if team.name == "Clean-up" else (d2,):
                for start, end in [(time(12), time(16)), (time(16), time(20)), (time(20), time(0))]:
                    # The silent disco shift over dinner time earns an extra €12.50 on top.
                    dinner = team.name == "Silent disco" and start == time(16)
                    shifts.append(Shift.objects.create(team=team, day=day, start=start, end=end,
                                                       capacity=rnd.randint(3, 6), location=f"{team.name} area",
                                                       shift_credential=disco_dinner if dinner else None,
                                                       notes="Dinner shift" if dinner else ""))
        for i in range(18):
            acc = add(vol_company, vol_t, status="pending" if i >= 14 else "approved", role="Volunteer", days=[d2])
            profile = VolunteerProfile.objects.create(person=acc, shirt_size=rnd.choice(["S", "M", "L", "XL"]))
            profile.preferred_teams.set(rnd.sample(teams, 2))
            profile.available_days.set([d2])
            if acc.status == "approved":
                for shift in rnd.sample([s for s in shifts if s.team in profile.preferred_teams.all()], 2):
                    if not shift.is_full():
                        ShiftAssignment.objects.get_or_create(shift=shift, person=acc, defaults={"self_assigned": True})

        approved = list(event.accreditations.filter(status="approved"))
        for acc in rnd.sample(approved, k=len(approved) // 2):
            services.process_scan(event, acc.token)
        for acc in rnd.sample(approved, k=3):
            services.process_scan(event, acc.token, z["VIP"])
        services.process_scan(event, "not-a-real-ticket")
        log(event, "Demo data loaded")
        self.stdout.write(self.style.SUCCESS(f"Created “{event.name}” → /e/{event.slug}/"))
