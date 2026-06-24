from django.shortcuts import get_object_or_404, render
from .models import Event, Entrance, AccessLevel, AccessEntry
from django.views.generic import ListView


def event(request, pk):
    event = get_object_or_404(Event, pk=pk)
    access_entries = event.access_entries.all()
    return render(
        request, "events/event.html", {"event": event, "access_entries": access_entries}
    )


class EventListView(ListView):
    model = Event
    template_name = "events/event_list.html"
    context_object_name = "events"
    ordering = ["date"]
