from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.forms import modelformset_factory
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accreditation.models import Accreditation
from artists.models import Artist, Performance
from crew.models import Shift

from .forms import DayLabelForm, EventForm
from .helpers import get_event, render_event, visible_events
from .models import Event, EventDay, Membership, log
from .permissions import MANAGER, Access, can_create_events, event_view


def event_list(request):
    today = timezone.localdate()
    events = visible_events(request.user)
    # Door staff with a single event go straight to the scanner.
    if not request.user.is_superuser and events.count() == 1:
        only = events.get()
        if Access(request.user, only).only_scans:
            return redirect("scanner", only.slug)
    events = events.annotate(
        people=Count(
            "accreditations",
            filter=Q(accreditations__status=Accreditation.APPROVED),
            distinct=True,
        ),
        pending=Count(
            "accreditations",
            filter=Q(accreditations__status=Accreditation.PENDING),
            distinct=True,
        ),
        artist_count=Count("artists", distinct=True),
    )
    return render(
        request,
        "core/event_list.html",
        {
            "upcoming": events.filter(end_date__gte=today).order_by("start_date"),
            "past": events.filter(end_date__lt=today).order_by("-start_date"),
            "can_create": can_create_events(request.user),
        },
    )


def event_create(request):
    if not can_create_events(request.user):
        raise PermissionDenied("Only administrators can create events.")
    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        if not request.user.is_superuser:
            Membership.objects.create(user=request.user, event=event, role=MANAGER)
        log(event, "Event created", request.user)
        messages.success(request, "Event created. Next: set up zones and credentials.")
        return redirect("zones", event.slug)
    return render(request, "core/event_form.html", {"form": form})


@event_view()
def dashboard(request, slug):
    event = get_event(slug)
    if request.access.only_scans:
        return redirect("scanner", event.slug)
    people = event.accreditations.all()
    approved = people.filter(status=Accreditation.APPROVED)

    by_type = (
        event.accreditation_types.annotate(
            total=Count("accreditations", filter=Q(accreditations__status="approved")),
            arrived=Count(
                "accreditations",
                filter=Q(
                    accreditations__status="approved",
                    accreditations__first_check_in_at__isnull=False,
                ),
            ),
        )
        .filter(total__gt=0)
    )

    shifts = Shift.objects.filter(team__event=event).annotate(n=Count("assignments"))
    capacity = shifts.aggregate(c=Sum("capacity"))["c"] or 0
    filled = sum(min(s.n, s.capacity) for s in shifts)

    today = timezone.localdate()
    show_day = event.days.filter(date=today).first() or event.days.first()
    performances = (
        Performance.objects.filter(day=show_day)
        .select_related("artist", "stage")
        .order_by("start")
        if show_day
        else []
    )

    artists = event.artists.all()
    stats = {
        "approved": approved.count(),
        "pending": people.filter(status=Accreditation.PENDING).count(),
        "arrived": approved.filter(first_check_in_at__isnull=False).count(),
        "inside": approved.filter(is_inside=True).count(),
        "companies": event.companies.count(),
        "artists": artists.count(),
        "advanced": artists.filter(advancing_status=Artist.COMPLETE).count(),
        "slots": capacity,
        "filled": filled,
    }
    return render_event(
        request,
        event,
        "core/dashboard.html",
        {
            "stats": stats,
            "by_type": by_type,
            "pending": people.filter(status=Accreditation.PENDING)
            .select_related("type", "company")
            .order_by("submitted_at")[:6],
            "activity": event.activity.select_related("actor")[:12],
            "show_day": show_day,
            "performances": performances,
        },
        section="dashboard",
    )


DayFormSet = modelformset_factory(EventDay, form=DayLabelForm, extra=0)


@event_view('settings')
def event_settings(request, slug):
    event = get_event(slug)
    form = EventForm(request.POST or None, instance=event, prefix="event")
    days = DayFormSet(
        request.POST or None, queryset=event.days.all(), prefix="days"
    )
    if request.method == "POST" and form.is_valid() and days.is_valid():
        form.save()
        days.save()
        event.refresh_from_db()
        log(event, "Event details updated", request.user)
        messages.success(request, "Event details saved.")
        return redirect("event_settings", event.slug)
    return render_event(
        request,
        event,
        "core/event_settings.html",
        {"form": form, "days": days},
        section="settings",
    )


@event_view('settings')
@require_POST
def event_delete(request, slug):
    event = get_event(slug)
    if request.POST.get("confirm", "").strip() != event.name:
        messages.error(request, "Type the event name exactly to delete it.")
        return redirect("event_settings", event.slug)
    event.delete()
    messages.success(request, f"“{event.name}” deleted.")
    return redirect("event_list")
