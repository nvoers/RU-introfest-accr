from django import forms

from core.forms import COLOR
from core.helpers import EventModelForm

from .models import Accreditation, AccreditationType, Company, Contingent, Item, TypeItem, Zone

CHECKS = forms.CheckboxSelectMultiple


class ZoneForm(EventModelForm):
    class Meta:
        model = Zone
        fields = ["name", "code", "color", "order"]
        widgets = {"color": COLOR}


class ItemForm(EventModelForm):
    class Meta:
        model = Item
        fields = ["name", "kind", "default_amount", "description"]
        widgets = {"default_amount": forms.NumberInput(attrs={"step": "0.01", "min": 0})}

    def clean(self):
        data = super().clean()
        if data.get("kind") == Item.PAYMENT_CARD:
            if data.get("default_amount") is None:
                self.add_error("default_amount", "Set the standard amount on this card (can be 0).")
        else:
            data["default_amount"] = None
        return data

    def save(self, commit=True):
        became_card = (
            self.instance.pk
            and "kind" in self.changed_data
            and self.cleaned_data["kind"] == Item.PAYMENT_CARD
        )
        item = super().save(commit=commit)
        if item.is_payment_card and "default_amount" in self.changed_data:
            # Shift credentials without their own amount use this default.
            from crew import perks

            for default in item.typeitem_set.filter(amount__isnull=True).select_related("type"):
                perks.sync_for_credential(default.type)
        if became_card:
            # An existing item turned into a payment card: quantities meant "number of
            # items" before, so credentials now give one card at the default amount,
            # and people who already have it get the default amount instead of €0.
            item.typeitem_set.update(quantity=1, amount=None)
            item.handouts.filter(amount__isnull=True).update(amount=item.default_amount)
        return item


class TypeForm(EventModelForm):
    """Credential type with its zones, one quantity field per item and an amount per payment card."""

    event_querysets = {"zones": "zones"}

    class Meta:
        model = AccreditationType
        fields = ["name", "color", "zones", "requires_approval", "order"]
        widgets = {"color": COLOR, "zones": CHECKS}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = {}
        if self.instance.pk:
            current = {
                d.item_id: d for d in self.instance.default_items.select_related("item")
            }
        self.item_fields = []
        for item in self.event.items.all():
            name = f"item_{item.pk}"
            existing = current.get(item.pk)
            if item.is_payment_card:
                # Empty = no card for this credential; a value = card with that amount.
                self.fields[name] = forms.DecimalField(
                    label=f"{item.name} (€)",
                    min_value=0,
                    max_digits=8,
                    decimal_places=2,
                    required=False,
                    initial=existing.card_amount() if existing else None,
                    widget=forms.NumberInput(
                        attrs={"step": "0.01", "placeholder": f"{item.default_amount or 0:.2f}"}
                    ),
                    help_text="Empty = no card",
                )
            else:
                self.fields[name] = forms.IntegerField(
                    label=item.name,
                    min_value=0,
                    required=False,
                    initial=existing.quantity if existing else 0,
                )
            self.item_fields.append(name)
        self.cards = {i.pk for i in self.event.items.all() if i.is_payment_card}

    def save(self, commit=True):
        obj = super().save(commit=commit)
        for name in self.item_fields:
            item_id = int(name.split("_")[1])
            value = self.cleaned_data.get(name)
            if item_id in self.cards and value is not None:
                TypeItem.objects.update_or_create(
                    type=obj, item_id=item_id, defaults={"quantity": 1, "amount": value}
                )
            elif item_id not in self.cards and value:
                TypeItem.objects.update_or_create(
                    type=obj, item_id=item_id, defaults={"quantity": value, "amount": None}
                )
            else:
                TypeItem.objects.filter(type=obj, item_id=item_id).delete()
        # Shifts may hand out this credential's items/zones: keep those people up to date.
        from crew import perks

        perks.sync_for_credential(obj)
        return obj

    def item_bound_fields(self):
        return [self[name] for name in self.item_fields]

    def plain_fields(self):
        return [f for f in self.visible_fields() if f.name not in self.item_fields]


class CompanyForm(EventModelForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "kind",
            "contact_name",
            "contact_email",
            "contact_phone",
            "portal_enabled",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class ContingentForm(forms.Form):
    """One quota field per accreditation type of the event."""

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        current = dict(company.contingents.values_list("type_id", "quota"))
        for type_ in company.event.accreditation_types.all():
            self.fields[f"type_{type_.pk}"] = forms.IntegerField(
                label=type_.name, min_value=0, required=False, initial=current.get(type_.pk, 0)
            )

    def save(self):
        for name, value in self.cleaned_data.items():
            type_id = int(name.split("_")[1])
            if value:
                Contingent.objects.update_or_create(
                    company=self.company, type_id=type_id, defaults={"quota": value}
                )
            else:
                Contingent.objects.filter(company=self.company, type_id=type_id).delete()


class PersonForm(EventModelForm):
    """Organiser form for an accreditation."""

    event_querysets = {
        "company": "companies",
        "type": "accreditation_types",
        "days": "days",
        "extra_zones": "zones",
    }
    send_ticket = forms.BooleanField(
        label="E-mail the e-ticket now", required=False, initial=True
    )

    class Meta:
        model = Accreditation
        fields = [
            "first_name",
            "last_name",
            "company",
            "type",
            "role",
            "email",
            "phone",
            "days",
            "extra_zones",
            "notes",
        ]
        labels = {"type": "Credential"}
        widgets = {
            "days": CHECKS,
            "extra_zones": CHECKS,
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].empty_label = "— No company —"
        self.fields["type"].empty_label = None
        if self.instance.pk:
            del self.fields["send_ticket"]

    def clean(self):
        data = super().clean()
        if data.get("send_ticket") and not data.get("email"):
            self.add_error("email", "An e-mail address is needed to send the ticket.")
        return data


class PartnerPersonForm(forms.ModelForm):
    """What a partner fills in on the portal. Types are limited to their contingents."""

    class Meta:
        model = Accreditation
        fields = ["first_name", "last_name", "type", "role", "email", "phone", "days"]
        labels = {"type": "Credential"}
        widgets = {"days": CHECKS}
        help_texts = {"days": "Leave empty if they need access on all days."}

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.instance.company = company
        self.instance.event = company.event
        self.fields["type"].queryset = AccreditationType.objects.filter(
            contingent__company=company
        )
        self.fields["type"].empty_label = None
        self.fields["days"].queryset = company.event.days.all()
        self.fields["email"].required = True

    def clean_type(self):
        type_ = self.cleaned_data["type"]
        contingent = self.company.contingents.filter(type=type_).first()
        used = (
            self.company.accreditations.active()
            .filter(type=type_)
            .exclude(pk=self.instance.pk)
            .count()
        )
        if contingent is None or used >= contingent.quota:
            raise forms.ValidationError(
                f"Your contingent for {type_} is full ({contingent.quota if contingent else 0})."
            )
        return type_


class RejectForm(forms.Form):
    reason = forms.CharField(max_length=300, required=False)
