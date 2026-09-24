import csv
import io
from collections import OrderedDict

from django.contrib import messages
from django.db.models import Count, Prefetch, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from hospitality.forms import HospitalityEntryForm, RiderForm
from hospitality.models import HospitalityEntry, RiderEntry, Space, SpaceEntry

from .forms import (
    AccessEntryForm,
    AccessLevelForm,
    EntranceForm,
    EventForm,
    ImportForm,
    SpaceForm,
)
from .models import AccessEntry, Event


def redirect_next(request, fallback):
    """Redirect to ?next= / POST next when it is a safe local URL."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}
    ):
        return redirect(target)
    return redirect(fallback)


def entries_for(event):
    return event.access_entries.select_related(
        "access_level", "entrance"
    ).prefetch_related(
        Prefetch(
            "space_entry",
            queryset=SpaceEntry.objects.select_related("space"),
        ),
        Prefetch(
            "hospitality_items",
            queryset=HospitalityEntry.objects.select_related("type"),
        ),
    )


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def event_list(request):
    active = ~Q(access_entries__status=AccessEntry.CANCELLED)
    events = Event.objects.annotate(
        entry_count=Count("access_entries", distinct=True),
        ticket_count=Sum("access_entries__number_of_tickets", filter=active),
        arrived_count=Sum(
            "access_entries__number_of_tickets",
            filter=Q(access_entries__status=AccessEntry.ARRIVED),
        ),
    )
    today = timezone.localdate()
    return render(
        request,
        "events/event_list.html",
        {
            "upcoming": events.filter(date__gte=today).order_by("date", "name"),
            "past": events.filter(date__lt=today).order_by("-date", "name"),
        },
    )


def event_form(request, pk=None):
    event = get_object_or_404(Event, pk=pk) if pk else None
    form = EventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        event = form.save()
        messages.success(
            request, f"Event “{event.name}” {'updated' if pk else 'created'}."
        )
        return redirect("event_detail" if pk else "event_setup", pk=event.pk)
    return render(request, "events/form.html", {"form": form, "event": event})


@require_POST
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.POST.get("confirm_name", "").strip() != event.name:
        messages.error(request, "Type the event name exactly to delete it.")
        return redirect("event_edit", pk=event.pk)
    event.delete()
    messages.success(request, f"Event “{event.name}” deleted.")
    return redirect("event_list")


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    entries = list(entries_for(event))

    by_level = OrderedDict()
    by_type = OrderedDict((label, [0, 0]) for label in AccessEntry.access_types)
    for level in event.access_levels.all():
        by_level[level.pk] = {"level": level, "tickets": 0, "arrived": 0}
    for entry in entries:
        if entry.is_cancelled:
            continue
        arrived = entry.number_of_tickets if entry.is_arrived else 0
        bucket = by_level.setdefault(
            entry.access_level_id, {"level": None, "tickets": 0, "arrived": 0}
        )
        bucket["tickets"] += entry.number_of_tickets
        bucket["arrived"] += arrived
        by_type[entry.access_type][0] += entry.number_of_tickets
        by_type[entry.access_type][1] += arrived

    hospitality = OrderedDict()
    for entry in entries:
        if entry.is_cancelled:
            continue
        for item in entry.hospitality_items.all():
            if item.type is None:
                continue
            row = hospitality.setdefault(
                item.type.pk, {"type": item.type, "total": 0, "issued": 0}
            )
            row["total"] += item.total
            row["issued"] += item.total if item.is_issued else 0

    return render(
        request,
        "events/event.html",
        {
            "event": event,
            "tab": "entries",
            "entries": entries,
            "stats": event.ticket_stats(),
            "by_level": [b for b in by_level.values() if b["tickets"]],
            "by_type": [
                {"label": k, "tickets": v[0], "arrived": v[1]}
                for k, v in by_type.items()
                if v[0]
            ],
            "hospitality": sorted(
                hospitality.values(), key=lambda r: r["type"].name.lower()
            ),
            "access_types": AccessEntry.access_types,
            "statuses": AccessEntry.status_choices,
        },
    )


SETUP_KINDS = OrderedDict(
    [
        (
            "levels",
            {
                "form": AccessLevelForm,
                "related": "access_levels",
                "label": "Access level",
                "plural": "Access levels",
                "help": "Which areas someone may enter. Shown as a colored badge.",
            },
        ),
        (
            "entrances",
            {
                "form": EntranceForm,
                "related": "entrances",
                "label": "Entrance",
                "plural": "Entrances",
                "help": "Where people pick up their accreditation.",
            },
        ),
        (
            "spaces",
            {
                "form": SpaceForm,
                "related": "spaces",
                "label": "Space",
                "plural": "Spaces",
                "help": "Dressing rooms and other rooms you can assign.",
            },
        ),
    ]
)


def event_setup(request, pk):
    event = get_object_or_404(Event, pk=pk)
    bound = {}  # (kind, item pk or "new") -> bound form with errors
    open_dialog = None

    if request.method == "POST":
        kind = request.POST.get("kind")
        action = request.POST.get("action")
        config = SETUP_KINDS.get(kind)
        if config is None:
            return redirect("event_setup", pk=event.pk)
        items = getattr(event, config["related"])
        item = None
        if request.POST.get("item"):
            item = get_object_or_404(items, pk=request.POST["item"])

        if action == "delete" and item is not None:
            item.delete()
            messages.success(request, f"{config['label']} “{item.name}” deleted.")
            return redirect("event_setup", pk=event.pk)

        key = item.pk if item else "new"
        form = config["form"](
            request.POST, instance=item, event=event, prefix=f"{kind}-{key}"
        )
        if form.is_valid():
            saved = form.save()
            verb = "updated" if item else "added"
            messages.success(request, f"{config['label']} “{saved.name}” {verb}.")
            return redirect("event_setup", pk=event.pk)
        bound[(kind, key)] = form
        open_dialog = f"dlg-{kind}-{key}"

    sections = []
    for kind, config in SETUP_KINDS.items():
        rows = []
        items = getattr(event, config["related"]).annotate(
            usage=Count(
                "space_entry" if kind == "spaces" else "access_entries",
                distinct=True,
            )
        )
        for item in items:
            form = bound.get((kind, item.pk)) or config["form"](
                instance=item, event=event, prefix=f"{kind}-{item.pk}"
            )
            rows.append({"item": item, "form": form})
        sections.append(
            {
                "kind": kind,
                **config,
                "rows": rows,
                "new_form": bound.get((kind, "new"))
                or config["form"](event=event, prefix=f"{kind}-new"),
            }
        )

    return render(
        request,
        "events/setup.html",
        {
            "event": event,
            "tab": "setup",
            "sections": sections,
            "open_dialog": open_dialog,
        },
    )


def checkin(request, pk):
    event = get_object_or_404(Event, pk=pk)
    entries = entries_for(event).order_by("name")
    recent = event.access_entries.filter(
        status=AccessEntry.ARRIVED, checked_in_at__isnull=False
    ).select_related("access_level").order_by("-checked_in_at")[:8]
    return render(
        request,
        "events/checkin.html",
        {
            "event": event,
            "tab": "checkin",
            "entries": entries,
            "recent": recent,
            "stats": event.ticket_stats(),
        },
    )


def event_print(request, pk):
    event = get_object_or_404(Event, pk=pk)
    entries = entries_for(event).exclude(status=AccessEntry.CANCELLED)
    return render(
        request,
        "events/print.html",
        {"event": event, "entries": entries, "now": timezone.localtime()},
    )


CSV_COLUMNS = [
    "name",
    "organisation",
    "type",
    "tickets",
    "access_level",
    "entrance",
    "spaces",
    "hospitality",
    "email",
    "phone",
    "notes",
    "status",
    "checked_in_at",
]


def event_export(request, pk):
    event = get_object_or_404(Event, pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    filename = f"{slugify(event.name) or 'event'}-accreditations.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # BOM so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerow(CSV_COLUMNS)
    for entry in entries_for(event):
        writer.writerow(
            [
                entry.name,
                entry.organisation,
                entry.access_type,
                entry.number_of_tickets,
                entry.access_level.name if entry.access_level else "",
                entry.entrance.name if entry.entrance else "",
                "; ".join(space.name for space in entry.spaces),
                "; ".join(
                    f"{h.total}x {h.type.name}"
                    for h in entry.hospitality_items.all()
                    if h.type
                ),
                entry.email,
                entry.phone,
                entry.notes,
                entry.status,
                timezone.localtime(entry.checked_in_at).strftime("%Y-%m-%d %H:%M")
                if entry.checked_in_at
                else "",
            ]
        )
    return response


def event_import(request, pk):
    event = get_object_or_404(Event, pk=pk)
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        raw = form.cleaned_data["file"].read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        created, problems = import_entries(event, text)
        if created:
            messages.success(
                request,
                f"Imported {created} accreditation{'s' if created != 1 else ''}.",
            )
        for problem in problems[:10]:
            messages.warning(request, problem)
        if len(problems) > 10:
            messages.warning(request, f"…and {len(problems) - 10} more warnings.")
        if created:
            return redirect("event_detail", pk=event.pk)
    return render(
        request,
        "events/import.html",
        {"event": event, "form": form, "tab": "entries", "columns": CSV_COLUMNS},
    )


def import_entries(event, text):
    """Create entries from CSV text. Returns (created_count, [warnings])."""
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames or "name" not in [
        (f or "").strip().lower() for f in reader.fieldnames
    ]:
        return 0, ["The file needs a header row with at least a “name” column."]

    levels = {lvl.name.lower(): lvl for lvl in event.access_levels.all()}
    entrances = {ent.name.lower(): ent for ent in event.entrances.all()}
    types = {t.lower(): t for t in AccessEntry.access_types}
    created, problems = 0, []

    for line, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        name = row.get("name")
        if not name:
            continue
        entry = AccessEntry(
            event=event,
            name=name[:200],
            organisation=row.get("organisation", "")[:200],
            email=row.get("email", "")[:254],
            phone=row.get("phone", "")[:40],
            notes=row.get("notes", ""),
        )
        kind = row.get("type", "")
        if kind:
            if kind.lower() in types:
                entry.access_type = types[kind.lower()]
            else:
                problems.append(f"Row {line}: unknown type “{kind}”, used Crew.")
        tickets = row.get("tickets", "")
        if tickets:
            if tickets.isdigit() and int(tickets) > 0:
                entry.number_of_tickets = int(tickets)
            else:
                problems.append(f"Row {line}: invalid tickets “{tickets}”, used 1.")
        for column, lookup, attr in (
            ("access_level", levels, "access_level"),
            ("entrance", entrances, "entrance"),
        ):
            value = row.get(column, "")
            if value:
                if value.lower() in lookup:
                    setattr(entry, attr, lookup[value.lower()])
                else:
                    problems.append(
                        f"Row {line}: unknown {column.replace('_', ' ')} “{value}”."
                    )
        entry.save()
        created += 1
    return created, problems


# --------------------------------------------------------------------------
# Accreditations
# --------------------------------------------------------------------------


def entry_create(request, pk):
    event = get_object_or_404(Event, pk=pk)
    form = AccessEntryForm(request.POST or None, event=event)
    if request.method == "POST" and form.is_valid():
        entry = form.save()
        messages.success(request, f"Accreditation for “{entry.name}” added.")
        if "add_another" in request.POST:
            return redirect("entry_create", pk=event.pk)
        return redirect("entry_detail", pk=entry.pk)
    return render(
        request,
        "accreditatie/new.html",
        {"event": event, "form": form, "tab": "entries"},
    )


def entry_detail(request, pk):
    entry = get_object_or_404(
        AccessEntry.objects.select_related("event", "access_level", "entrance"),
        pk=pk,
    )
    event = entry.event
    forms = {
        "edit": AccessEntryForm(instance=entry, event=event, prefix="edit"),
        "hospitality": HospitalityEntryForm(entry=entry, prefix="hosp"),
        "rider": RiderForm(prefix="rider"),
    }
    open_dialog = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit":
            form = AccessEntryForm(
                request.POST, instance=entry, event=event, prefix="edit"
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Accreditation updated.")
                return redirect("entry_detail", pk=entry.pk)
            forms["edit"], open_dialog = form, "dlg-edit"
        elif action == "hospitality":
            form = HospitalityEntryForm(request.POST, entry=entry, prefix="hosp")
            if form.is_valid():
                form.save()
                return redirect("entry_detail", pk=entry.pk)
            forms["hospitality"], open_dialog = form, "dlg-hospitality"
        elif action == "rider":
            form = RiderForm(request.POST, prefix="rider")
            if form.is_valid():
                form.instance.entry = entry
                form.save()
                return redirect("entry_detail", pk=entry.pk)
            forms["rider"] = form
        else:
            return entry_action(request, entry, action)

    assigned = SpaceEntry.objects.filter(entry=entry).select_related("space")
    return render(
        request,
        "accreditatie/access_entry.html",
        {
            "entry": entry,
            "event": event,
            "tab": "entries",
            "forms": forms,
            "open_dialog": open_dialog,
            "assigned": assigned,
            "available_spaces": event.spaces.exclude(
                pk__in=assigned.values("space_id")
            ),
            "hospitality_items": entry.hospitality_items.select_related("type"),
            "rider_items": entry.rider_items.all(),
        },
    )


def entry_action(request, entry, action):
    """Small one-click actions on the detail page."""
    post = request.POST
    if action == "delete":
        event_pk = entry.event_id
        entry.delete()
        messages.success(request, f"Accreditation for “{entry.name}” deleted.")
        return redirect("event_detail", pk=event_pk)
    if action == "space_add":
        space = get_object_or_404(Space, pk=post.get("space"), event=entry.event)
        SpaceEntry.objects.get_or_create(entry=entry, space=space)
    elif action == "space_remove":
        SpaceEntry.objects.filter(entry=entry, pk=post.get("item")).delete()
    elif action == "hospitality_toggle":
        item = get_object_or_404(HospitalityEntry, entry=entry, pk=post.get("item"))
        item.status = (
            HospitalityEntry.NOT_ISSUED if item.is_issued else HospitalityEntry.ISSUED
        )
        item.save(update_fields=["status"])
    elif action == "hospitality_issue_all":
        entry.hospitality_items.update(status=HospitalityEntry.ISSUED)
    elif action == "hospitality_remove":
        HospitalityEntry.objects.filter(entry=entry, pk=post.get("item")).delete()
    elif action == "rider_remove":
        RiderEntry.objects.filter(entry=entry, pk=post.get("item")).delete()
    return redirect("entry_detail", pk=entry.pk)


@require_POST
def entry_status(request, pk):
    entry = get_object_or_404(AccessEntry, pk=pk)
    status = request.POST.get("status")
    if status not in AccessEntry.status_choices:
        messages.error(request, "Unknown status.")
    elif status != entry.status:
        entry.set_status(status)
        if status == AccessEntry.ARRIVED:
            tickets = entry.number_of_tickets
            level = f" · {entry.access_level.name}" if entry.access_level else ""
            messages.success(
                request,
                f"{entry.name} checked in — {tickets} ticket{'s' if tickets != 1 else ''}{level}.",
            )
        elif status == AccessEntry.CANCELLED:
            messages.info(request, f"{entry.name} cancelled.")
        else:
            messages.info(request, f"{entry.name} set to not arrived.")
    return redirect_next(request, reverse("entry_detail", args=[entry.pk]))
