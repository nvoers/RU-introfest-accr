from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST

from hospitality.models import Space, SpaceEntry
from .models import Event, Entrance, AccessLevel, AccessEntry
from django.views.generic import ListView, TemplateView, DetailView
from .forms import (
    NewEventForm,
    NewAccessLevelForm,
    NewAccessEntryForm,
    EditAccessEntryForm,
    NewSpaceForm,
)


class EventDetailView(TemplateView):
    template_name = "events/event.html"

    def get_event_context(self, event, accessForm=None, spaceForm=None):
        return {
            "event": event,
            "access_entries": event.access_entries.all(),
            "access_levels": event.access_levels.all(),
            "spaces": event.spaces.all(),
            "accessForm": accessForm or NewAccessLevelForm(),
            "spaceForm": spaceForm or NewSpaceForm(event=event),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        context.update(self.get_event_context(event))
        return context

    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        submitted_form = request.POST.get("submitted_form")

        if submitted_form == "access_level":
            accessForm = NewAccessLevelForm(request.POST)
            spaceForm = NewSpaceForm(event=event)

            if accessForm.is_valid():
                AccessLevel.objects.create(
                    name=accessForm.cleaned_data["name"],
                    color=accessForm.cleaned_data["color"],
                    event=event,
                )
                return redirect("event_detail", pk=event.pk)

            return render(
                request,
                self.template_name,
                self.get_event_context(
                    event, accessForm=accessForm, spaceForm=spaceForm
                ),
            )

        if submitted_form == "space":
            accessForm = NewAccessLevelForm()
            spaceForm = NewSpaceForm(request.POST, event=event)

            if spaceForm.is_valid():
                Space.objects.create(name=spaceForm.cleaned_data["name"], event=event)
                return redirect("event_detail", pk=event.pk)

            return render(
                request,
                self.template_name,
                self.get_event_context(
                    event, accessForm=accessForm, spaceForm=spaceForm
                ),
            )

        accessForm = NewAccessLevelForm(request.POST)
        spaceForm = NewSpaceForm(request.POST, event=event)

        return render(
            request,
            self.template_name,
            self.get_event_context(event, accessForm=accessForm, spaceForm=spaceForm),
        )


class EventListView(ListView):
    model = Event
    template_name = "events/event_list.html"
    context_object_name = "events"
    ordering = ["date"]


class NewEventView(TemplateView):
    template_name = "events/new.html"

    def get(self, request, *args, **kwargs):
        form = NewEventForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request, *args, **kwargs):
        form = NewEventForm(request.POST)
        if form.is_valid():
            event = Event.objects.create(
                name=form.cleaned_data["name"],
                date=form.cleaned_data["date"],
                start_time=form.cleaned_data["start_time"],
                end_time=form.cleaned_data["end_time"],
                location=form.cleaned_data["location"],
            )
            return redirect("event_detail", pk=event.pk)
        return render(request, self.template_name, {"form": form})


class AccessEntryDetailView(TemplateView):
    template_name = "accreditatie/access_entry.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entry = get_object_or_404(AccessEntry, pk=self.kwargs["pk"])
        form = EditAccessEntryForm(instance=entry, event=entry.event)
        spaces = entry.event.spaces.all()

        context.update(
            {
                "entry": entry,
                "form": form,
                "spaces": spaces,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        entry = get_object_or_404(AccessEntry, pk=self.kwargs["pk"])

        if "toggle_status" in request.POST:
            if entry.status == AccessEntry.ARRIVED:
                entry.status = AccessEntry.NOT_ARRIVED
            else:
                entry.status = AccessEntry.ARRIVED
            entry.save(update_fields=["status", "updated_at"])
            return redirect("access_entry_detail", pk=entry.pk)

        form = EditAccessEntryForm(request.POST, instance=entry, event=entry.event)
        if form.is_valid():
            entry.name = form.cleaned_data["name"]
            entry.event = form.cleaned_data["event"]
            entry.access_type = form.cleaned_data["type"]
            entry.number_of_tickets = form.cleaned_data["number_of_tickets"]
            entry.entrance = form.cleaned_data["entrance"]
            entry.access_level = form.cleaned_data["access_level"]
            entry.full_clean()
            entry.save()
            return redirect("access_entry_detail", pk=entry.pk)

        context = self.get_context_data(**kwargs)
        context["form"] = form
        return render(request, self.template_name, context)


class NewAccessEntryView(TemplateView):
    template_name = "accreditatie/new.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        entrances = event.entrances.all()
        access_levels = event.access_levels.all()
        form = NewAccessEntryForm(event=event)

        context.update(
            {
                "event": event,
                "entrances": entrances,
                "access_levels": access_levels,
                "form": form,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        form = NewAccessEntryForm(request.POST, event=event)
        if form.is_valid():
            access_entry = AccessEntry.objects.create(
                name=form.cleaned_data["name"],
                event=event,
                access_type=form.cleaned_data["type"],
                number_of_tickets=form.cleaned_data["number_of_tickets"],
                entrance=form.cleaned_data["entrance"],
                access_level=form.cleaned_data["access_level"],
            )
            return redirect("event_detail", pk=event.pk)

        entrances = event.entrances.all()
        access_levels = event.access_levels.all()
        return render(
            request,
            self.template_name,
            {
                "event": event,
                "entrances": entrances,
                "access_levels": access_levels,
                "form": form,
            },
        )


@require_POST
def assign_space(request, pk):
    entry = get_object_or_404(AccessEntry, pk=pk)
    space_id = request.POST.get("space_id")
    space = get_object_or_404(Space, id=space_id)

    SpaceEntry.objects.get_or_create(entry=entry, space=space)

    return redirect("access_entry_detail", pk=entry.id)
