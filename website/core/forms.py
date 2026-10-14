from django import forms

from .models import Event, EventDay

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
COLOR = forms.TextInput(attrs={"type": "color"})


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "venue", "start_date", "end_date", "description"]
        widgets = {
            "start_date": DATE,
            "end_date": DATE,
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end:
            if end < start:
                self.add_error("end_date", "The end date can't be before the start date.")
            elif (end - start).days > 60:
                self.add_error("end_date", "Events can span at most 60 days.")
        return data


class DayLabelForm(forms.ModelForm):
    class Meta:
        model = EventDay
        fields = ["label"]
        widgets = {"label": forms.TextInput(attrs={"placeholder": "e.g. Build-up"})}
