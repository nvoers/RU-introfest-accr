from django.contrib import messages
from django.db.models import Count, Prefetch, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from accreditation.models import Accreditation
from accreditation.services import absolute
from core.helpers import crud_page, get_event, render_event
from core.models import log

from .forms import CrewSettingsForm, ShiftForm, TeamForm
from .models import CrewSettings, Shift, ShiftAssignment


def teams(request, slug):
    event = get_event(slug)
    return crud_page(
        request,
        event,
        queryset=event.teams.annotate(n=Count("shifts")),
        form_class=TeamForm,
        template="crew/teams.html",
        noun="team",
        section="teams",
    )


def shift_queryset(event):
    return (
        Shift.objects.filter(team__event=event)
        .select_related("team", "day")
        .prefetch_related(
            Prefetch(
                "assignments",
                queryset=ShiftAssignment.objects.select_related("person"),
            )
        )
    )


def shifts(request, slug):
    event = get_event(slug)
    if not event.teams.exists():
        messages.info(request, "Create a team first – shifts belong to a team.")
        return redirect("teams", event.slug)

    bound, open_dialog = {}, None
    if request.method == "POST":
        action = request.POST.get("action")
        shift = None
        if request.POST.get("item"):
            shift = get_object_or_404(Shift, pk=request.POST["item"], team__event=event)
        if action == "delete" and shift:
            shift.delete()
            messages.success(request, "Shift deleted.")
            return redirect(request.get_full_path())
        if action == "assign" and shift:
            person = get_object_or_404(
                event.accreditations, pk=request.POST.get("person"), status=Accreditation.APPROVED
            )
            ShiftAssignment.objects.get_or_create(shift=shift, person=person)
            messages.success(request, f"{person.full_name} added to the shift.")
            return redirect(request.get_full_path())
        if action == "unassign" and shift:
            shift.assignments.filter(pk=request.POST.get("assignment")).delete()
            return redirect(request.get_full_path())
        key = shift.pk if shift else "new"
        form = ShiftForm(request.POST, instance=shift, event=event, prefix=f"f-{key}")
        if form.is_valid():
            form.save()
            log(event, f"Shift {form.instance} saved", request.user)
            messages.success(request, "Shift saved.")
            return redirect(request.get_full_path())
        bound[key], open_dialog = form, f"dlg-{key}"

    qs = shift_queryset(event)
    team_id, day_id = request.GET.get("team", ""), request.GET.get("day", "")
    if team_id:
        qs = qs.filter(team_id=team_id)
    if day_id:
        qs = qs.filter(day_id=day_id)
    rows = [
        {"obj": s, "form": bound.get(s.pk) or ShiftForm(instance=s, event=event, prefix=f"f-{s.pk}")}
        for s in qs
    ]
    candidates = (
        event.accreditations.filter(status=Accreditation.APPROVED)
        .select_related("type", "company")
        .order_by("first_name")
    )
    initial = {"team": team_id or None, "day": day_id or None}
    return render_event(
        request,
        event,
        "crew/shifts.html",
        {
            "rows": rows,
            "new_form": bound.get("new") or ShiftForm(event=event, prefix="f-new", initial=initial),
            "open_dialog": open_dialog,
            "team_id": team_id,
            "day_id": day_id,
            "candidates": candidates,
        },
        section="shifts",
    )


def roster(request, slug):
    event = get_event(slug)
    days = list(event.days.all())
    today = timezone.localdate()
    day = (
        next((d for d in days if str(d.pk) == request.GET.get("day")), None)
        or next((d for d in days if d.date == today), None)
        or (days[0] if days else None)
    )
    by_team = {}
    for shift in shift_queryset(event).filter(day=day):
        by_team.setdefault(shift.team, []).append(shift)
    return render_event(
        request,
        event,
        "crew/roster.html",
        {"days": days, "day": day, "by_team": by_team.items()},
        section="roster",
    )


def volunteers(request, slug):
    event = get_event(slug)
    settings = CrewSettings.for_event(event)
    form = CrewSettingsForm(request.POST or None, instance=settings)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Volunteer settings saved.")
        return redirect("volunteers", event.slug)
    people = (
        event.accreditations.filter(volunteer__isnull=False)
        .select_related("volunteer", "type")
        .prefetch_related("volunteer__preferred_teams", "volunteer__available_days")
        .annotate(
            n_shifts=Count("shift_assignments", distinct=True),
        )
        .order_by("status", "first_name")
    )
    hours = {}
    for a in ShiftAssignment.objects.filter(person__in=people).select_related("shift"):
        hours[a.person_id] = hours.get(a.person_id, 0) + a.shift.hours
    capacity = Shift.objects.filter(team__event=event).aggregate(c=Sum("capacity"))["c"] or 0
    return render_event(
        request,
        event,
        "crew/volunteers.html",
        {
            "form": form,
            "settings": settings,
            "people": people,
            "hours": hours,
            "signup_link": absolute(reverse("volunteer_signup", args=[settings.signup_token])),
            "capacity": capacity,
        },
        section="volunteers",
    )
