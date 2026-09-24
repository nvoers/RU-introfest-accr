from django import forms

from .models import HospitalityEntry, RiderEntry, Types


class HospitalityTypeForm(forms.ModelForm):
    class Meta:
        model = Types
        fields = ["name", "type", "value"]
        widgets = {"value": forms.NumberInput(attrs={"step": "0.01", "min": 0})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["value"].required = False
        self.fields["value"].label = "Card value (€)"

    def clean_value(self):
        return self.cleaned_data["value"] or 0


class HospitalityEntryForm(forms.ModelForm):
    class Meta:
        model = HospitalityEntry
        fields = ["type", "amount"]
        widgets = {"amount": forms.NumberInput(attrs={"min": 1})}

    def __init__(self, *args, entry, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.entry = entry
        taken = entry.hospitality_items.values_list("type_id", flat=True)
        self.fields["type"].queryset = Types.objects.exclude(pk__in=taken)
        self.fields["type"].required = True
        self.fields["type"].empty_label = "Choose an item"


class RiderForm(forms.ModelForm):
    class Meta:
        model = RiderEntry
        fields = ["rider"]
        labels = {"rider": "Rider item"}
        widgets = {
            "rider": forms.Textarea(
                attrs={"rows": 2, "placeholder": "e.g. 6× still water on stage"}
            )
        }
