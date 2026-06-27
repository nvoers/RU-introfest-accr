from django import forms


class NewEventForm(forms.Form):
    name = forms.CharField(label="Event Name", max_length=100)
    date = forms.DateField(
        label="Event Date", widget=forms.DateInput(attrs={"type": "date"})
    )
    start_time = forms.TimeField(
        label="Event Start Time", widget=forms.TimeInput(format="%H:%M")
    )
    end_time = forms.TimeField(
        label="Event End Time", widget=forms.TimeInput(format="%H:%M")
    )
    location = forms.CharField(label="Event Location", max_length=200)


class NewAccessLevelForm(forms.Form):
    name = forms.CharField(label="Access Level Name", max_length=100)
    color = forms.CharField(
        label="Access Level Color",
        max_length=7,
        widget=forms.TextInput(attrs={"type": "color"}),
    )


class NewSpaceForm(forms.Form):
    name = forms.CharField(label="Space Name", max_length=100)
    event = forms.ModelChoiceField(
        label="Event", queryset=None, empty_label="Select an event"
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        from .models import Event

        self.fields["event"].queryset = Event.objects.all()
        if event is not None:
            self.fields["event"].queryset = Event.objects.filter(pk=event.pk)
            self.fields["event"].initial = event.pk
            self.fields["event"].widget = forms.HiddenInput()


class NewAccessEntryForm(forms.Form):
    name = forms.CharField(label="Name", max_length=100)
    event = forms.ModelChoiceField(
        label="Event", queryset=None, empty_label="Select an event"
    )
    type = forms.ChoiceField(
        label="Type",
        choices=[("Artist", "Artist"), ("Crew", "Crew"), ("Guest", "Guest")],
    )
    number_of_tickets = forms.IntegerField(label="Number of Tickets", min_value=1)
    entrance = forms.ModelChoiceField(label="Entrance", queryset=None)
    access_level = forms.ModelChoiceField(label="Access Level", queryset=None)

    def __init__(self, *args, **kwargs):
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        from .models import AccessLevel, Entrance, Event

        self.fields["event"].queryset = Event.objects.all()
        if event is not None:
            self.fields["event"].queryset = Event.objects.filter(pk=event.pk)
            self.fields["event"].initial = event.pk
            self.fields["event"].widget = forms.HiddenInput()
            self.fields["entrance"].queryset = Entrance.objects.filter(event=event)
            self.fields["access_level"].queryset = AccessLevel.objects.filter(
                event=event
            )


class EditAccessEntryForm(forms.Form):
    name = forms.CharField(label="Name", max_length=100)
    event = forms.ModelChoiceField(
        label="Event", queryset=None, empty_label="Select an event"
    )
    type = forms.ChoiceField(
        label="Type",
        choices=[("Artist", "Artist"), ("Crew", "Crew"), ("Guest", "Guest")],
    )
    number_of_tickets = forms.IntegerField(label="Number of Tickets", min_value=1)
    entrance = forms.ModelChoiceField(label="Entrance", queryset=None)
    access_level = forms.ModelChoiceField(label="Access Level", queryset=None)

    def __init__(self, *args, **kwargs):
        instance = kwargs.pop("instance", None)
        event = kwargs.pop("event", None)
        super().__init__(*args, **kwargs)
        from .models import AccessLevel, Entrance, Event

        self.fields["event"].queryset = Event.objects.all()
        if event is not None:
            self.fields["event"].queryset = Event.objects.filter(pk=event.pk)
            self.fields["event"].initial = event.pk
            self.fields["event"].widget = forms.HiddenInput()
            self.fields["entrance"].queryset = Entrance.objects.filter(event=event)
            self.fields["access_level"].queryset = AccessLevel.objects.filter(
                event=event
            )

        if instance is not None:
            self.initial["name"] = instance.name
            self.initial["event"] = instance.event
            self.initial["type"] = instance.access_type
            self.initial["number_of_tickets"] = instance.number_of_tickets
            self.initial["entrance"] = instance.entrance
            self.initial["access_level"] = instance.access_level
            self.fields["name"].initial = instance.name
            self.fields["event"].initial = instance.event
            self.fields["type"].initial = instance.access_type
            self.fields["number_of_tickets"].initial = instance.number_of_tickets
            self.fields["entrance"].initial = instance.entrance
            self.fields["access_level"].initial = instance.access_level
