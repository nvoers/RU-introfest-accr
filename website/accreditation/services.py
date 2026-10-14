"""Business rules for accreditations: approval, e-mails and scanning."""

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from core.models import log

from .models import Accreditation, Scan


def absolute(path):
    return f"{settings.SITE_URL}{path}"


def send_ticket(acc):
    if not acc.email or not acc.is_approved:
        return False
    zones = ", ".join(z.name for z in acc.all_zones()) or "—"
    send_mail(
        subject=f"Your accreditation for {acc.event.name}",
        message=(
            f"Hi {acc.first_name},\n\n"
            f"Your accreditation for {acc.event.name} has been approved.\n\n"
            f"Credential: {acc.type.name}\nZones: {zones}\n\n"
            f"Show this e-ticket at the accreditation desk:\n{absolute(acc.ticket_url())}\n\n"
            "See you there!"
        ),
        from_email=None,
        recipient_list=[acc.email],
    )
    acc.ticket_sent_at = timezone.now()
    acc.save(update_fields=["ticket_sent_at"])
    return True


def send_rejection(acc):
    if not acc.email:
        return
    reason = f"\nReason: {acc.rejection_reason}\n" if acc.rejection_reason else ""
    send_mail(
        subject=f"Accreditation request for {acc.event.name}",
        message=(
            f"Hi {acc.first_name},\n\nUnfortunately your accreditation request for "
            f"{acc.event.name} was not approved.{reason}\n"
            "Please contact the person who registered you if you have questions."
        ),
        from_email=None,
        recipient_list=[acc.email],
    )


def send_portal_invite(company):
    if not company.contact_email:
        return False
    send_mail(
        subject=f"Request accreditations for {company.event.name}",
        message=(
            f"Hi {company.contact_name or company.name},\n\n"
            f"You can register your people for {company.event.name} here:\n"
            f"{absolute(company.portal_url())}\n\n"
            "Keep this link private – anyone with it can request accreditations "
            "on behalf of your company."
        ),
        from_email=None,
        recipient_list=[company.contact_email],
    )
    return True


def approve(acc, user=None, notify=True):
    acc.set_status(Accreditation.APPROVED, user)
    acc.apply_default_items()
    log(acc.event, f"Approved {acc.full_name} ({acc.type})", user, url=acc.get_absolute_url())
    if notify:
        send_ticket(acc)


def reject(acc, user=None, reason="", notify=True):
    acc.set_status(Accreditation.REJECTED, user, reason)
    log(acc.event, f"Rejected {acc.full_name}", user, url=acc.get_absolute_url())
    if notify:
        send_rejection(acc)


def submit(acc, label=""):
    """Partner submits a draft: straight to approved if the type needs no approval."""
    if acc.type.requires_approval:
        acc.set_status(Accreditation.PENDING)
        log(acc.event, f"{acc.company} requested {acc.full_name} ({acc.type})", label=label,
            url=acc.get_absolute_url())
    else:
        acc.submitted_at = timezone.now()
        approve(acc)


def find_by_code(event, code):
    code = (code or "").strip()
    # Accept a pasted ticket URL as well as the bare token.
    if "/t/" in code:
        code = code.rstrip("/").rsplit("/", 1)[-1]
    return (
        Accreditation.objects.filter(event=event, token=code)
        .select_related("type", "company")
        .first()
    ), code


@transaction.atomic
def process_scan(event, code, zone=None, direction=Scan.IN, user=None):
    """Validate a scanned code at a checkpoint and record it. Returns a dict for the UI."""
    acc, code = find_by_code(event, code)
    today = timezone.localdate()
    result, message = Scan.OK, ""

    if acc is None:
        result, message = Scan.DENIED, "Unknown code"
    elif acc.status != Accreditation.APPROVED:
        result, message = Scan.DENIED, f"Accreditation is {acc.get_status_display().lower()}"
    elif not acc.valid_on(today) and event.days.filter(date=today).exists():
        result, message = Scan.DENIED, "Not valid today"
    elif zone is not None and zone not in acc.all_zones():
        result, message = Scan.DENIED, f"No access to {zone.name}"
    elif direction == Scan.IN and acc.is_inside and zone is None:
        result, message = Scan.WARNING, "Already checked in – possible double use"
    elif direction == Scan.OUT and not acc.is_inside and zone is None:
        result, message = Scan.WARNING, "Was not checked in"

    first_time = False
    if acc is not None and result != Scan.DENIED and zone is None:
        acc.is_inside = direction == Scan.IN
        fields = ["is_inside"]
        if direction == Scan.IN and acc.first_check_in_at is None:
            acc.first_check_in_at = timezone.now()
            fields.append("first_check_in_at")
            first_time = True
        acc.save(update_fields=fields)

    Scan.objects.create(
        event=event,
        accreditation=acc,
        zone=zone,
        code=code[:200],
        direction=direction,
        result=result,
        message=message,
        user=user if user and user.is_authenticated else None,
    )

    payload = {"result": result, "message": message, "first_time": first_time}
    if acc is not None:
        payload.update(
            {
                "id": acc.pk,
                "name": acc.full_name,
                "company": acc.company.name if acc.company else "",
                "role": acc.role,
                "type": acc.type.name,
                "color": acc.type.color,
                "zones": [z.code or z.name for z in acc.all_zones()],
                "items": [
                    {"id": i.pk, "label": f"{i.quantity}× {i.item.name}", "issued": i.is_issued}
                    for i in acc.items.select_related("item")
                ],
                "url": acc.get_absolute_url(),
            }
        )
    return payload
