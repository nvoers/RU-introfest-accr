from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.models import Event, EventDay, new_token


class Zone(models.Model):
    """An access area that is checked at a scan point (Backstage, Pit, VIP…)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=6, blank=True, help_text="Short code printed on badges, e.g. BS."
    )
    color = models.CharField(max_length=7, default="#64748b")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Item(models.Model):
    """Something handed out with an accreditation: wristband, voucher, parking ticket."""

    WRISTBAND, VOUCHER, PAYMENT_CARD, PARKING, MERCH, OTHER = (
        "wristband",
        "voucher",
        "payment_card",
        "parking",
        "merch",
        "other",
    )
    KINDS = {
        WRISTBAND: "Wristband",
        VOUCHER: "Voucher / token",
        PAYMENT_CARD: "Payment card",
        PARKING: "Parking ticket",
        MERCH: "Merchandise",
        OTHER: "Other",
    }

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KINDS.items(), default=VOUCHER)
    description = models.CharField(max_length=200, blank=True)
    default_amount = models.DecimalField(
        "default amount",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Payment cards only: credit loaded on each card unless the credential "
        "or person says otherwise.",
    )

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name

    @property
    def is_payment_card(self):
        return self.kind == self.PAYMENT_CARD


class AccreditationType(models.Model):
    """A credential: decides zones, default days and default items."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="accreditation_types"
    )
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#2563eb")
    zones = models.ManyToManyField(Zone, blank=True, related_name="types")
    requires_approval = models.BooleanField(
        default=True,
        help_text="Requests from portals wait for approval before a ticket is sent.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class TypeItem(models.Model):
    type = models.ForeignKey(
        AccreditationType, on_delete=models.CASCADE, related_name="default_items"
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Payment cards: credit for this credential (overrides the item default).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["type", "item"], name="unique_type_item")
        ]

    def card_amount(self):
        if self.amount is not None:
            return self.amount
        return self.item.default_amount or Decimal("0")


class Company(models.Model):
    """A partner that requests accreditations: supplier, band, press outlet…"""

    PARTNER, SUPPLIER, ARTIST, PRESS, VOLUNTEERS, INTERNAL = (
        "partner",
        "supplier",
        "artist",
        "press",
        "volunteers",
        "internal",
    )
    KINDS = {
        PARTNER: "Partner",
        SUPPLIER: "Supplier",
        ARTIST: "Artist",
        PRESS: "Press",
        VOLUNTEERS: "Volunteers",
        INTERNAL: "Internal",
    }

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="companies")
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=20, choices=KINDS.items(), default=PARTNER)
    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    token = models.CharField(max_length=40, unique=True, default=new_token)
    portal_enabled = models.BooleanField(
        default=True, help_text="Allow the contact to request accreditations online."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("company_detail", args=[self.event.slug, self.pk])

    def portal_url(self):
        return reverse("portal_home", args=[self.token])

    def usage(self):
        """[(contingent, used)] for every contingent of this company."""
        counts = {}
        for type_id in self.accreditations.exclude(
            status__in=Accreditation.NOT_COUNTED
        ).values_list("type_id", flat=True):
            counts[type_id] = counts.get(type_id, 0) + 1
        return [(c, counts.get(c.type_id, 0)) for c in self.contingents.all()]


class Contingent(models.Model):
    """How many accreditations of a type a company may request."""

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="contingents"
    )
    type = models.ForeignKey(AccreditationType, on_delete=models.CASCADE)
    quota = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["type__order", "type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "type"], name="unique_contingent"
            )
        ]

    def __str__(self):
        return f"{self.company}: {self.quota}× {self.type}"


class AccreditationQuerySet(models.QuerySet):
    def active(self):
        return self.exclude(status__in=Accreditation.NOT_COUNTED)

    def search(self, query):
        for word in query.split():
            self = self.filter(
                Q(first_name__icontains=word)
                | Q(last_name__icontains=word)
                | Q(email__icontains=word)
                | Q(company__name__icontains=word)
                | Q(role__icontains=word)
            )
        return self


class Accreditation(models.Model):
    DRAFT, PENDING, APPROVED, REJECTED, CANCELLED = (
        "draft",
        "pending",
        "approved",
        "rejected",
        "cancelled",
    )
    STATUSES = {
        DRAFT: "Draft",
        PENDING: "Pending approval",
        APPROVED: "Approved",
        REJECTED: "Rejected",
        CANCELLED: "Cancelled",
    }
    NOT_COUNTED = (REJECTED, CANCELLED)

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="accreditations"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accreditations",
    )
    type = models.ForeignKey(
        AccreditationType, on_delete=models.PROTECT, related_name="accreditations"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    role = models.CharField(
        "function", max_length=100, blank=True, help_text="e.g. Tour manager, Driver"
    )
    days = models.ManyToManyField(
        EventDay,
        blank=True,
        related_name="accreditations",
        help_text="Leave empty for all days.",
    )
    extra_zones = models.ManyToManyField(
        Zone,
        blank=True,
        related_name="extra_accreditations",
        help_text="Zones on top of what the type gives.",
    )
    # Filled automatically from the person's shifts (see crew.perks).
    shift_zones = models.ManyToManyField(
        Zone, blank=True, related_name="shift_accreditations", editable=False
    )
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUSES.items(), default=APPROVED)
    rejection_reason = models.CharField(max_length=300, blank=True)
    token = models.CharField(max_length=40, unique=True, default=new_token)

    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    ticket_sent_at = models.DateTimeField(null=True, blank=True)
    first_check_in_at = models.DateTimeField(null=True, blank=True)
    is_inside = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccreditationQuerySet.as_manager()

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse("person_detail", args=[self.event.slug, self.pk])

    def ticket_url(self):
        return reverse("ticket", args=[self.token])

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self):
        parts = [self.first_name[:1], self.last_name[:1]]
        return "".join(p for p in parts if p).upper() or "?"

    @property
    def is_approved(self):
        return self.status == self.APPROVED

    @property
    def is_editable_by_partner(self):
        return self.status in (self.DRAFT, self.REJECTED)

    def all_zones(self):
        zones = {z.pk: z for z in self.type.zones.all()}
        zones.update({z.pk: z for z in self.extra_zones.all()})
        zones.update({z.pk: z for z in self.shift_zones.all()})
        return sorted(zones.values(), key=lambda z: (z.order, z.name))

    def valid_days(self):
        days = list(self.days.all())
        return days or list(self.event.days.all())

    def valid_on(self, date):
        days = list(self.days.all())
        return not days or any(d.date == date for d in days)

    def apply_default_items(self):
        """Add the type's default items that are missing (never removes any)."""
        have = set(self.items.values_list("item_id", flat=True))
        AccreditationItem.objects.bulk_create(
            [
                AccreditationItem(
                    accreditation=self,
                    item=d.item,
                    quantity=d.quantity,
                    amount=d.card_amount() if d.item.is_payment_card else None,
                )
                for d in self.type.default_items.select_related("item")
                if d.item_id not in have
            ]
        )

    def set_status(self, status, user=None, reason=""):
        self.status = status
        self.rejection_reason = reason if status == self.REJECTED else ""
        if status == self.PENDING:
            self.submitted_at = timezone.now()
        if status in (self.APPROVED, self.REJECTED):
            self.decided_at = timezone.now()
            self.decided_by = user if user and user.is_authenticated else None
        self.save()


class AccreditationItem(models.Model):
    accreditation = models.ForeignKey(
        Accreditation, on_delete=models.CASCADE, related_name="items"
    )
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="handouts")
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(
        "credit",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Payment cards: amount on the card for this person.",
    )
    # Added on top by the person's shifts (see crew.perks); recalculated automatically.
    shift_quantity = models.PositiveIntegerField(default=0, editable=False)
    shift_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0"), editable=False
    )
    from_shifts = models.BooleanField(default=False, editable=False)
    issued_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["item__kind", "item__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["accreditation", "item"], name="unique_accreditation_item"
            )
        ]

    @property
    def is_issued(self):
        return self.issued_at is not None

    @property
    def is_payment_card(self):
        return self.item.is_payment_card

    @property
    def total_quantity(self):
        return self.quantity + self.shift_quantity

    @property
    def total_amount(self):
        """Total on the card(s): own amount × cards, plus what shifts add."""
        return (self.amount or Decimal("0")) * self.quantity + self.shift_amount

    @property
    def has_shift_part(self):
        return bool(self.shift_quantity or self.shift_amount)

    @property
    def label(self):
        if self.is_payment_card:
            cards = f"{self.quantity}× " if self.quantity > 1 else ""
            return f"{cards}{self.item.name} · {money(self.total_amount)}"
        return f"{self.total_quantity}× {self.item.name}"


def money(value):
    from django.conf import settings

    symbol = getattr(settings, "CURRENCY_SYMBOL", "€")
    return f"{symbol}{(value or Decimal('0')):,.2f}"


class Scan(models.Model):
    IN, OUT = "in", "out"
    DIRECTIONS = {IN: "In", OUT: "Out"}
    OK, WARNING, DENIED = "ok", "warning", "denied"
    RESULTS = {OK: "Allowed", WARNING: "Allowed with warning", DENIED: "Denied"}

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="scans")
    accreditation = models.ForeignKey(
        Accreditation,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="scans",
    )
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=200)
    direction = models.CharField(max_length=3, choices=DIRECTIONS.items(), default=IN)
    result = models.CharField(max_length=10, choices=RESULTS.items())
    message = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
