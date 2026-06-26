from django.shortcuts import get_object_or_404, render, redirect
from .models import Event, Entrance, AccessLevel, AccessEntry
from django.views.generic import ListView, TemplateView, DetailView
from .forms import NewEventForm, NewAccessLevelForm, NewAccessEntryForm


class EventDetailView(TemplateView):
    template_name = "events/event.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        access_entries = event.access_entries.all()
        access_levels = event.access_levels.all()
        form = NewAccessLevelForm()

        context.update(
            {
                "event": event,
                "access_entries": access_entries,
                "access_levels": access_levels,
                "form": form,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        event = get_object_or_404(Event, pk=self.kwargs["pk"])
        form = NewAccessLevelForm(request.POST)
        if form.is_valid():
            AccessLevel.objects.create(
                name=form.cleaned_data["name"],
                color=form.cleaned_data["color"],
                event=event,
            )
            return redirect("event_detail", pk=event.pk)

        access_entries = event.access_entries.all()
        access_levels = event.access_levels.all()
        return render(
            request,
            self.template_name,
            {
                "event": event,
                "access_entries": access_entries,
                "access_levels": access_levels,
                "form": form,
            },
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


class AccessEntryDetailView(DetailView):
    model = AccessEntry
    template_name = "accreditatie/access_entry_detail.html"
    context_object_name = "access_entry"


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
