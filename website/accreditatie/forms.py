from django import forms

from hospitality.models import Space

from .models import AccessEntry, AccessLevel, Entrance, Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "location", "date", "start_time", "end_time"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }


class EventScopedForm(forms.ModelForm):
    """ModelForm for things that belong to an event, with names unique per event."""

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.instance.event = event

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clashes = self._meta.model.objects.filter(
            event=self.event, name__iexact=name
        ).exclude(pk=self.instance.pk)
        if clashes.exists():
            raise forms.ValidationError(
                f"“{name}” already exists for this event."
            )
        return name


class AccessLevelForm(EventScopedForm):
    class Meta:
        model = AccessLevel
        fields = ["name", "color"]
        help_texts = {"color": ""}
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}


class EntranceForm(EventScopedForm):
    class Meta:
        model = Entrance
        fields = ["name"]


class SpaceForm(EventScopedForm):
    class Meta:
        model = Space
        fields = ["name"]


class AccessEntryForm(forms.ModelForm):
    class Meta:
        model = AccessEntry
        fields = [
            "name",
            "organisation",
            "access_type",
            "number_of_tickets",
            "access_level",
            "entrance",
            "email",
            "phone",
            "notes",
        ]
        widgets = {
            "number_of_tickets": forms.NumberInput(attrs={"min": 1}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.event = event
        self.fields["access_level"].queryset = event.access_levels.all()
        self.fields["entrance"].queryset = event.entrances.all()
        self.fields["access_level"].empty_label = "No access level"
        self.fields["entrance"].empty_label = "No entrance"
        self.fields["name"].widget.attrs["autofocus"] = True


class ImportForm(forms.Form):
    file = forms.FileField(
        label="CSV file",
        help_text=(
            "Columns: name, organisation, type, tickets, access_level, entrance, "
            "email, phone, notes. Only name is required."
        ),
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )
