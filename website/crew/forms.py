from django import forms

from accreditation.models import Accreditation
from core.forms import COLOR, TIME
from core.helpers import EventModelForm

from . import perks
from .models import CrewSettings, Shift, Team, VolunteerProfile


class TeamForm(EventModelForm):
    event_querysets = {"shift_credential": "accreditation_types"}

    class Meta:
        model = Team
        fields = ["name", "color", "lead", "shift_credential", "description"]
        widgets = {"color": COLOR, "description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["shift_credential"].empty_label = "Nothing extra"

    def save(self, commit=True):
        team = super().save(commit=commit)
        if "shift_credential" in self.changed_data:
            perks.sync_shifts(team.shifts.all())
        return team


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ["team", "day", "start", "end", "location", "capacity", "shift_credential",
                  "open_for_signup", "notes"]
        widgets = {"start": TIME, "end": TIME}

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = event.teams.all()
        self.fields["day"].queryset = event.days.all()
        self.fields["shift_credential"].queryset = event.accreditation_types.all()
        self.fields["team"].empty_label = None
        self.fields["day"].empty_label = None
        self.fields["shift_credential"].empty_label = "Nothing extra"

    def save(self, commit=True):
        shift = super().save(commit=commit)
        if {"shift_credential", "team"} & set(self.changed_data):
            perks.sync_shifts([shift])
        return shift


class CrewSettingsForm(forms.ModelForm):
    class Meta:
        model = CrewSettings
        fields = ["signup_open", "accreditation_type", "max_shifts_per_person", "intro"]
        widgets = {"intro": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accreditation_type"].queryset = self.instance.event.accreditation_types.all()

    def clean(self):
        data = super().clean()
        if data.get("signup_open") and not data.get("accreditation_type"):
            self.add_error("accreditation_type", "Choose which credential volunteers get.")
        return data


class VolunteerSignupForm(forms.Form):
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=40)
    preferred_teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.none(), widget=forms.CheckboxSelectMultiple, required=False,
        label="Where would you like to help?",
    )
    available_days = forms.ModelMultipleChoiceField(
        queryset=None, widget=forms.CheckboxSelectMultiple, label="Which days are you available?"
    )
    shirt_size = forms.ChoiceField(choices=[("", "—")] + list(VolunteerProfile.SHIRT_SIZES.items()),
                                   required=False, label="T-shirt size")
    motivation = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False,
                                 label="Anything we should know?")

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.fields["preferred_teams"].queryset = event.teams.all()
        self.fields["available_days"].queryset = event.days.all()

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Accreditation.objects.filter(
            event=self.event, email__iexact=email, volunteer__isnull=False
        ).exists():
            raise forms.ValidationError("You already signed up with this e-mail address.")
        return email
