"""Public pages, reachable through secret links without logging in."""

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accreditation import services
from accreditation.forms import PartnerPersonForm
from accreditation.models import Accreditation, Company
from artists.forms import AdvancingForm, HotelRoomForm, TransportForm
from artists.models import Artist
from core.models import log
from crew.forms import VolunteerSignupForm
from crew.models import CrewSettings, Shift, ShiftAssignment, VolunteerProfile


def get_company(token):
    company = get_object_or_404(Company.objects.select_related("event"), token=token)
    if not company.portal_enabled:
        raise Http404("This portal is closed.")
    return company


@login_not_required
def portal_home(request, token):
    company = get_company(token)
    artist = getattr(company, "artist", None)
    tab = request.GET.get("tab", "people")
    if tab not in ("people", "advancing", "logistics") or (tab != "people" and not artist):
        tab = "people"
    label = company.contact_name or company.name
    here = f"{reverse('portal_home', args=[token])}?tab={tab}"

    editing = None
    if request.GET.get("edit"):
        editing = get_object_or_404(company.accreditations, pk=request.GET["edit"])
        if not editing.is_editable_by_partner:
            editing = None

    forms = {
        "person": PartnerPersonForm(instance=editing, company=company, prefix="p"),
    }
    if artist:
        forms["advancing"] = AdvancingForm(instance=artist, prefix="adv")
        forms["transport"] = TransportForm(artist=artist, prefix="transport")
        forms["room"] = HotelRoomForm(artist=artist, prefix="room")
    open_dialog = "dlg-person" if editing else None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "person":
            form = PartnerPersonForm(request.POST, instance=editing, company=company, prefix="p")
            if form.is_valid():
                acc = form.save(commit=False)
                if not acc.pk:
                    acc.status = Accreditation.DRAFT
                elif acc.status == Accreditation.REJECTED:
                    acc.status = Accreditation.DRAFT
                acc.save()
                form.save_m2m()
                messages.success(request, f"{acc.full_name} saved as draft. Submit when your list is complete.")
                return redirect(here)
            forms["person"], open_dialog = form, "dlg-person"
        elif action == "delete":
            acc = get_object_or_404(company.accreditations, pk=request.POST.get("item"))
            if acc.status in (Accreditation.DRAFT, Accreditation.REJECTED, Accreditation.PENDING):
                acc.delete()
                messages.info(request, f"{acc.full_name} removed.")
            return redirect(here)
        elif action == "submit":
            drafts = company.accreditations.filter(status=Accreditation.DRAFT).select_related("type", "event")
            n = 0
            with transaction.atomic():
                for acc in drafts:
                    services.submit(acc, label=label)
                    n += 1
            messages.success(
                request,
                f"{n} request{'s' if n != 1 else ''} submitted. You'll be e-mailed when they're reviewed."
                if n else "There were no drafts to submit.",
            )
            return redirect(here)
        elif artist and action == "advancing":
            form = AdvancingForm(request.POST, request.FILES, instance=artist, prefix="adv")
            if form.is_valid():
                artist = form.save(commit=False)
                if "submit" in request.POST:
                    artist.advancing_status = Artist.SUBMITTED
                    log(company.event, f"{artist} submitted their advancing", label=label,
                        url=artist.get_absolute_url())
                elif artist.advancing_status == Artist.NOT_STARTED:
                    artist.advancing_status = Artist.IN_PROGRESS
                artist.save()
                messages.success(request, "Advancing submitted – thank you!" if "submit" in request.POST
                                 else "Saved. You can come back later to finish.")
                return redirect(here)
            forms["advancing"] = form
        elif artist and action in ("transport", "room"):
            cls = TransportForm if action == "transport" else HotelRoomForm
            form = cls(request.POST, artist=artist, prefix=action)
            if form.is_valid():
                obj = form.save(commit=False)
                if action == "room":
                    obj.hotel = ""  # chosen by the organiser
                obj.save()
                log(company.event, f"{artist} requested {'transport' if action == 'transport' else 'a hotel room'}",
                    label=label, url=artist.get_absolute_url())
                messages.success(request, "Request sent.")
                return redirect(here)
            forms[action], open_dialog = form, f"dlg-{action}"
        elif artist and action in ("transport_delete", "room_delete"):
            related = artist.transports if action == "transport_delete" else artist.rooms
            related.filter(pk=request.POST.get("item"), status="requested").delete()
            return redirect(here)

    people = company.accreditations.select_related("type").prefetch_related("days")
    usage = company.usage()
    return render(
        request,
        "portal/home.html",
        {
            "company": company,
            "event": company.event,
            "artist": artist,
            "tab": tab,
            "forms": forms,
            "people": people,
            "usage": usage,
            "can_add": any(used < c.quota for c, used in usage),
            "drafts": sum(1 for p in people if p.status == Accreditation.DRAFT),
            "editing": editing,
            "person_action": f"?tab=people&edit={editing.pk}" if editing else "?tab=people",
            "open_dialog": open_dialog,
            "performances": artist.performances.select_related("stage", "day") if artist else [],
            "transports": artist.transports.select_related("day") if artist else [],
            "rooms": artist.rooms.all() if artist else [],
        },
    )


def shifts_for(acc):
    """Shifts a volunteer may still claim."""
    profile = getattr(acc, "volunteer", None)
    qs = Shift.objects.filter(team__event=acc.event, open_for_signup=True).select_related("team", "day")
    if profile:
        teams = list(profile.preferred_teams.all())
        days = list(profile.available_days.all())
        if teams:
            qs = qs.filter(team__in=teams)
        if days:
            qs = qs.filter(day__in=days)
    mine = set(acc.shift_assignments.values_list("shift_id", flat=True))
    return [s for s in qs if s.pk not in mine and not s.is_full()]


def overlaps(a, b):
    if a.day_id != b.day_id:
        return False
    def span(s):
        start = s.start.hour * 60 + s.start.minute
        end = s.end.hour * 60 + s.end.minute
        return start, end if end > start else end + 1440
    a0, a1 = span(a)
    b0, b1 = span(b)
    return a0 < b1 and b0 < a1


@login_not_required
def ticket(request, token):
    acc = get_object_or_404(
        Accreditation.objects.select_related("event", "type", "company"), token=token
    )
    is_crew = hasattr(acc, "volunteer") or acc.shift_assignments.exists()
    settings = CrewSettings.objects.filter(event=acc.event).first()

    if request.method == "POST" and acc.is_approved:
        action = request.POST.get("action")
        mine = list(acc.shift_assignments.select_related("shift"))
        if action == "claim":
            shift = get_object_or_404(Shift, pk=request.POST.get("shift"), team__event=acc.event,
                                      open_for_signup=True)
            limit = settings.max_shifts_per_person if settings else 4
            if shift.is_full():
                messages.error(request, "Sorry, that shift just filled up.")
            elif len(mine) >= limit:
                messages.error(request, f"You can sign up for at most {limit} shifts.")
            elif any(overlaps(shift, a.shift) for a in mine):
                messages.error(request, "That shift overlaps with one you already have.")
            else:
                ShiftAssignment.objects.get_or_create(shift=shift, person=acc, defaults={"self_assigned": True})
                messages.success(request, f"You're on the {shift.team} shift, {shift.day} {shift.start:%H:%M}.")
        elif action == "drop":
            acc.shift_assignments.filter(pk=request.POST.get("assignment"), self_assigned=True).delete()
            messages.info(request, "Shift removed.")
        return redirect("ticket", token)

    return render(
        request,
        "portal/ticket.html",
        {
            "acc": acc,
            "event": acc.event,
            "zones": acc.all_zones(),
            "days": acc.valid_days(),
            "handouts": acc.items.select_related("item"),
            "is_crew": is_crew,
            "my_shifts": acc.shift_assignments.select_related("shift__team", "shift__day").order_by(
                "shift__day__date", "shift__start"
            ),
            "open_shifts": shifts_for(acc) if is_crew and acc.is_approved else [],
        },
    )


@login_not_required
def volunteer_signup(request, token):
    settings = get_object_or_404(CrewSettings.objects.select_related("event"), signup_token=token)
    event = settings.event
    if not settings.signup_open or settings.accreditation_type is None:
        return render(request, "portal/signup_closed.html", {"event": event})
    form = VolunteerSignupForm(request.POST or None, event=event)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            acc = Accreditation.objects.create(
                event=event,
                company=settings.volunteers_company(),
                type=settings.accreditation_type,
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                phone=data["phone"],
                role="Volunteer",
                status=Accreditation.DRAFT,
            )
            acc.days.set(data["available_days"])
            profile = VolunteerProfile.objects.create(
                person=acc, shirt_size=data["shirt_size"], motivation=data["motivation"]
            )
            profile.preferred_teams.set(data["preferred_teams"])
            profile.available_days.set(data["available_days"])
            services.submit(acc, label=acc.full_name)
        return redirect("ticket", acc.token)
    return render(
        request,
        "portal/signup.html",
        {"event": event, "settings": settings, "form": form, "teams": event.teams.all()},
    )
