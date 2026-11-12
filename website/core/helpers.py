"""Shared plumbing for organiser views."""

from django import forms
from django.contrib import messages
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Event, log


class EventModelForm(forms.ModelForm):
    """ModelForm that knows its event: scopes related querysets and sets instance.event."""

    #: field name -> related manager name on Event, used to scope choices.
    event_querysets = {}

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        if hasattr(self.instance, "event_id") and not self.instance.event_id:
            self.instance.event = event
        for field, related in self.event_querysets.items():
            if field in self.fields:
                self.fields[field].queryset = getattr(event, related).all()


def get_event(slug):
    return get_object_or_404(Event, slug=slug)


def nav_counts(event):
    from accreditation.models import Accreditation
    from artists.models import Artist

    return {
        "pending": event.accreditations.filter(status=Accreditation.PENDING).count(),
        "advancing": event.artists.filter(advancing_status=Artist.SUBMITTED).count(),
    }


def visible_events(user):
    events = Event.objects.all()
    if not user.is_superuser:
        events = events.filter(memberships__user=user)
    return events


def render_event(request, event, template, context=None, section=""):
    from .permissions import Access

    access = getattr(request, "access", None) or Access(request.user, event)
    area = getattr(request, "area", None)
    context = dict(context or {})
    context.setdefault("event", event)
    context.setdefault("nav", nav_counts(event))
    context.setdefault("section", section)
    context["access"] = access
    context["can"] = access.flags()
    # Pages the user may only look at hide their forms and edit buttons (see app.css);
    # the server refuses the changes either way.
    context["readonly"] = area is not None and not access.can(area, edit=True)
    return render(request, template, context)


def safe_next(request, fallback):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}):
        return redirect(target)
    return redirect(fallback)


def crud_page(
    request,
    event,
    *,
    queryset,
    form_class,
    template,
    noun,
    section="settings",
    context=None,
):
    """A list page where items are created, edited and deleted in modal dialogs.

    Forms are prefixed "f-new" / "f-<pk>"; a failed submit re-opens its dialog.
    """
    bound = {}
    open_dialog = None

    if request.method == "POST":
        obj = None
        if request.POST.get("item"):
            obj = get_object_or_404(queryset, pk=request.POST["item"])
        if request.POST.get("action") == "delete" and obj is not None:
            try:
                obj.delete()
            except ProtectedError:
                messages.error(request, f"“{obj}” is still in use and can't be deleted.")
            else:
                log(event, f"Deleted {noun} “{obj}”", request.user)
                messages.success(request, f"{noun.capitalize()} “{obj}” deleted.")
            return redirect(request.path)

        key = obj.pk if obj else "new"
        form = form_class(
            request.POST, request.FILES, instance=obj, event=event, prefix=f"f-{key}"
        )
        if form.is_valid():
            saved = form.save()
            verb = "updated" if obj else "added"
            log(event, f"{noun.capitalize()} “{saved}” {verb}", request.user)
            messages.success(request, f"{noun.capitalize()} “{saved}” {verb}.")
            return redirect(request.path)
        bound[key] = form
        open_dialog = f"dlg-{key}"

    rows = [
        {
            "obj": obj,
            "form": bound.get(obj.pk)
            or form_class(instance=obj, event=event, prefix=f"f-{obj.pk}"),
        }
        for obj in queryset
    ]
    ctx = {
        "rows": rows,
        "new_form": bound.get("new") or form_class(event=event, prefix="f-new"),
        "open_dialog": open_dialog,
        "noun": noun,
    }
    ctx.update(context or {})
    return render_event(request, event, template, ctx, section=section)
