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
