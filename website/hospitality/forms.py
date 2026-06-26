from django import forms


class NewHospitalityTypeForm(forms.Form):
    name = forms.CharField(label="Name", max_length=100)
    type = forms.ChoiceField(
        label="Type",
        choices=[("coin", "Coin"), ("card", "Card"), ("none", "None")],
    )
    value = forms.DecimalField(
        label="Value",
        min_value=0,
        decimal_places=2,
        max_digits=10,
        required=False,
    )
