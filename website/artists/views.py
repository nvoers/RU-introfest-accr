from django.contrib import messages
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect

from accreditation.services import absolute
from core.helpers import crud_page, get_event, render_event
from core.models import log
from core.permissions import event_view

from .forms import (
    AdvancingForm,
    ArtistAdminForm,
    ArtistCreateForm,
    HotelRoomForm,
    PerformanceForm,
    StageForm,
    TransportForm,
)
from .models import Artist, HotelRoom, Performance, Transport


@event_view('setup')
def stages(request, slug):
    event = get_event(slug)
    return crud_page(
        request,
        event,
        queryset=event.stages.annotate(n=Count("performances")),
        form_class=StageForm,
        template="artists/stages.html",
        noun="stage",
    )


@event_view('artists')
def artist_list(request, slug):
    event = get_event(slug)
    form = ArtistCreateForm(request.POST or None, event=event, prefix="f-new")
    if request.method == "POST" and form.is_valid():
        artist = form.save()
        log(event, f"Artist “{artist}” added", request.user, url=artist.get_absolute_url())
        messages.success(request, f"{artist} added.")
        return redirect(artist)
    status = request.GET.get("status", "")
    artists = event.artists.select_related("company").prefetch_related(
        Prefetch("performances", queryset=Performance.objects.select_related("stage", "day"))
    ).annotate(
        n_party=Count("company__accreditations", distinct=True),
        n_transport=Count("transports", distinct=True),
        n_rooms=Count("rooms", distinct=True),
    )
    if status:
        artists = artists.filter(advancing_status=status)
    return render_event(
        request,
        event,
        "artists/artist_list.html",
        {
            "artists": artists,
            "new_form": form,
            "open_dialog": "dlg-new" if form.errors else None,
            "status": status,
            "statuses": Artist.ADVANCING,
        },
        section="artists",
    )


SUBFORMS = {
    "performance": (PerformanceForm, "performances"),
    "transport": (TransportForm, "transports"),
    "room": (HotelRoomForm, "rooms"),
}


@event_view('artists')
def artist_detail(request, slug, pk):
    event = get_event(slug)
    artist = get_object_or_404(event.artists.select_related("company"), pk=pk)
    forms = {
        "admin": ArtistAdminForm(instance=artist, prefix="admin"),
        "advancing": AdvancingForm(instance=artist, prefix="adv"),
        **{k: cls(artist=artist, prefix=k) for k, (cls, _) in SUBFORMS.items()},
    }
    open_dialog = None

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "admin":
            form = ArtistAdminForm(request.POST, instance=artist, prefix="admin")
            if form.is_valid():
                form.save()
                artist.company.name = artist.name
                artist.company.save(update_fields=["name"])
                messages.success(request, "Saved.")
                return redirect(artist)
            forms["admin"], open_dialog = form, "dlg-admin"
        elif action == "advancing":
            form = AdvancingForm(request.POST, request.FILES, instance=artist, prefix="adv")
            if form.is_valid():
                form.save()
                log(event, f"Advancing of {artist} updated", request.user, url=artist.get_absolute_url())
                messages.success(request, "Advancing saved.")
                return redirect(artist)
            forms["advancing"], open_dialog = form, "dlg-advancing"
        elif action in SUBFORMS:
            cls, _ = SUBFORMS[action]
            form = cls(request.POST, artist=artist, prefix=action)
            if form.is_valid():
                form.save()
                messages.success(request, "Added.")
                return redirect(artist)
            forms[action], open_dialog = form, f"dlg-{action}"
        elif action.endswith("_delete") or action.endswith("_status"):
            kind = action.rsplit("_", 1)[0]
            if kind in SUBFORMS:
                obj = get_object_or_404(getattr(artist, SUBFORMS[kind][1]), pk=request.POST.get("item"))
                if action.endswith("_delete"):
                    obj.delete()
                elif request.POST.get("status") in Transport.STATUSES:
                    obj.status = request.POST["status"]
                    obj.save(update_fields=["status"])
                return redirect(artist)
        elif action == "delete":
            company = artist.company
            artist.delete()
            company.delete()
            log(event, f"Artist “{artist}” deleted", request.user)
            messages.success(request, f"{artist} deleted.")
            return redirect("artist_list", event.slug)

    return render_event(
        request,
        event,
        "artists/artist_detail.html",
        {
            "artist": artist,
            "forms": forms,
            "open_dialog": open_dialog,
            "performances": artist.performances.select_related("stage", "day"),
            "transports": artist.transports.select_related("day"),
            "rooms": artist.rooms.all(),
            "party": artist.company.accreditations.select_related("type"),
            "usage": artist.company.usage(),
            "portal_link": absolute(artist.company.portal_url()),
        },
        section="artists",
    )


@event_view('artists')
def timetable(request, slug):
    event = get_event(slug)
    days = list(event.days.all())
    day = next((d for d in days if str(d.pk) == request.GET.get("day")), None)
    if day is None:
        with_shows = [d for d in days if d.performances.exists()]
        day = (with_shows or days or [None])[0]
    stages = list(event.stages.all())
    shows = list(
        Performance.objects.filter(day=day).select_related("artist", "stage")
    ) if day else []

    if shows:
        start = min(s.start_minutes for s in shows) // 60 * 60
        end = -(-max(s.end_minutes for s in shows) // 60) * 60
    else:
        start, end = 12 * 60, 24 * 60
    columns = []
    for stage in stages:
        blocks = []
        for show in shows:
            if show.stage_id == stage.pk:
                blocks.append(
                    {
                        "show": show,
                        "top": show.start_minutes - start,
                        "height": max(show.end_minutes - show.start_minutes, 15),
                    }
                )
        columns.append({"stage": stage, "blocks": blocks})
    hours = [(m - start, f"{(m // 60) % 24:02d}:00") for m in range(start, end + 1, 60)]
    return render_event(
        request,
        event,
        "artists/timetable.html",
        {
            "days": days,
            "day": day,
            "columns": columns,
            "hours": hours,
            "span": end - start,
        },
        section="timetable",
    )


@event_view('artists')
def logistics(request, slug):
    event = get_event(slug)
    if request.method == "POST":
        model = {"transport": Transport, "room": HotelRoom}.get(request.POST.get("kind"))
        if model and request.POST.get("status") in model.STATUSES:
            obj = get_object_or_404(model, pk=request.POST.get("item"), artist__event=event)
            obj.status = request.POST["status"]
            if model is HotelRoom and "hotel" in request.POST:
                obj.hotel = request.POST["hotel"][:200]
            obj.save()
        return redirect(request.get_full_path())
    return render_event(
        request,
        event,
        "artists/logistics.html",
        {
            "transports": Transport.objects.filter(artist__event=event).select_related("artist", "day"),
            "rooms": HotelRoom.objects.filter(artist__event=event).select_related("artist"),
        },
        section="logistics",
    )
