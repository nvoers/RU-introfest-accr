from django import forms

from accreditation.models import Company
from core.forms import COLOR, DATE, TIME
from core.helpers import EventModelForm

from .models import Artist, HotelRoom, Performance, Stage, Transport


class StageForm(EventModelForm):
    class Meta:
        model = Stage
        fields = ["name", "color", "order"]
        widgets = {"color": COLOR}


class ArtistCreateForm(EventModelForm):
    contact_name = forms.CharField(label="Tour manager / contact", max_length=200, required=False)
    contact_email = forms.EmailField(label="Contact e-mail", required=False)
    contact_phone = forms.CharField(label="Contact phone", max_length=40, required=False)

    class Meta:
        model = Artist
        fields = ["name", "agent"]

    def save(self, commit=True):
        artist = super().save(commit=False)
        artist.company = Company.objects.create(
            event=self.event,
            name=artist.name,
            kind=Company.ARTIST,
            contact_name=self.cleaned_data["contact_name"],
            contact_email=self.cleaned_data["contact_email"],
            contact_phone=self.cleaned_data["contact_phone"],
        )
        artist.save()
        return artist


class AdvancingForm(forms.ModelForm):
    class Meta:
        model = Artist
        fields = [
            "arrival",
            "party_size",
            "dressing_room",
            "technical_rider",
            "hospitality_rider",
            "rider_file",
        ]
        widgets = {
            "arrival": forms.Textarea(attrs={"rows": 3}),
            "technical_rider": forms.Textarea(attrs={"rows": 5}),
            "hospitality_rider": forms.Textarea(attrs={"rows": 5}),
        }


class ArtistAdminForm(forms.ModelForm):
    class Meta:
        model = Artist
        fields = ["name", "agent", "advancing_status", "internal_notes"]
        widgets = {"internal_notes": forms.Textarea(attrs={"rows": 3})}


class PerformanceForm(forms.ModelForm):
    class Meta:
        model = Performance
        fields = ["stage", "day", "start", "end", "changeover_minutes"]
        widgets = {"start": TIME, "end": TIME}

    def __init__(self, *args, artist, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.artist = artist
        self.fields["stage"].queryset = artist.event.stages.all()
        self.fields["day"].queryset = artist.event.days.all()
        self.fields["stage"].empty_label = None
        self.fields["day"].empty_label = None

    def clean(self):
        data = super().clean()
        stage, day, start, end = (data.get(k) for k in ("stage", "day", "start", "end"))
        if stage and day and start and end:
            probe = Performance(stage=stage, day=day, start=start, end=end)
            clash = (
                Performance.objects.filter(stage=stage, day=day)
                .exclude(pk=self.instance.pk)
                .select_related("artist")
            )
            for other in clash:
                if probe.start_minutes < other.end_minutes and other.start_minutes < probe.end_minutes:
                    raise forms.ValidationError(
                        f"Overlaps with {other.artist} ({other.start:%H:%M}–{other.end:%H:%M}) on {stage}."
                    )
        return data


class TransportForm(forms.ModelForm):
    class Meta:
        model = Transport
        fields = ["day", "time", "pickup", "dropoff", "passengers", "notes"]
        widgets = {"time": TIME}

    def __init__(self, *args, artist, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.artist = artist
        self.fields["day"].queryset = artist.event.days.all()
        self.fields["day"].empty_label = None
        self.fields["pickup"].widget.attrs["placeholder"] = "e.g. Schiphol Airport, arrivals 2"
        self.fields["dropoff"].widget.attrs["placeholder"] = "e.g. Festival backstage gate"


class HotelRoomForm(forms.ModelForm):
    class Meta:
        model = HotelRoom
        fields = ["room_type", "check_in", "check_out", "guests", "hotel", "notes"]
        widgets = {"check_in": DATE, "check_out": DATE}

    def __init__(self, *args, artist, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.artist = artist
        self.fields["hotel"].help_text = "Filled in by the organiser."

    def clean(self):
        data = super().clean()
        if data.get("check_in") and data.get("check_out") and data["check_out"] <= data["check_in"]:
            self.add_error("check_out", "Check-out must be after check-in.")
        return data
