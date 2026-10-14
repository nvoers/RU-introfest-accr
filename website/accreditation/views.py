import csv
import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.helpers import crud_page, get_event, render_event, safe_next
from core.models import log, new_token

from . import services
from .forms import (
    CompanyForm,
    ContingentForm,
    ItemForm,
    PersonForm,
    RejectForm,
    TypeForm,
    ZoneForm,
)
from .models import Accreditation, AccreditationItem, Company, Item, Scan, Zone

# --------------------------------------------------------------------- setup


def zones(request, slug):
    event = get_event(slug)
    return crud_page(
        request,
        event,
        queryset=event.zones.annotate(n_types=Count("types")),
        form_class=ZoneForm,
        template="accreditation/zones.html",
        noun="zone",
    )


def items(request, slug):
    event = get_event(slug)
    return crud_page(
        request,
        event,
        queryset=event.items.annotate(n=Count("handouts")),
        form_class=ItemForm,
        template="accreditation/items.html",
        noun="item",
    )


def types(request, slug):
    event = get_event(slug)
    return crud_page(
        request,
        event,
        queryset=event.accreditation_types.prefetch_related(
            "zones", "default_items__item"
        ).annotate(n=Count("accreditations")),
        form_class=TypeForm,
        template="accreditation/types.html",
        noun="credential",
    )


# -------------------------------------------------------------------- people


def people_queryset(event):
    return event.accreditations.select_related("type", "company").prefetch_related(
        "days"
    )


def people(request, slug):
    event = get_event(slug)
    if request.method == "POST":
        return bulk_action(request, event)

    qs = people_queryset(event)
    f = {k: request.GET.get(k, "") for k in ("q", "status", "type", "company", "inside")}
    if f["q"]:
        qs = qs.search(f["q"])
    if f["status"]:
        qs = qs.filter(status=f["status"])
    if f["type"]:
        qs = qs.filter(type_id=f["type"])
    if f["company"]:
        qs = qs.filter(company_id=f["company"]) if f["company"] != "none" else qs.filter(company=None)
    if f["inside"] == "yes":
        qs = qs.filter(is_inside=True)
    elif f["inside"] == "arrived":
        qs = qs.filter(first_check_in_at__isnull=False)

    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    counts = dict(
        event.accreditations.values_list("status").annotate(n=Count("id")).values_list("status", "n")
    )
    return render_event(
        request,
        event,
        "accreditation/people.html",
        {
            "page": page,
            "filters": f,
            "filtered": any(f.values()),
            "counts": counts,
            "statuses": Accreditation.STATUSES,
        },
        section="people",
    )


def bulk_action(request, event):
    ids = request.POST.getlist("ids")
    action = request.POST.get("bulk")
    if request.POST.get("single"):
        ids, action = [request.POST["single"]], "approve"
    selected = event.accreditations.filter(pk__in=ids).select_related("type", "event")
    done = 0
    for acc in selected:
        if action == "approve" and acc.status != Accreditation.APPROVED:
            services.approve(acc, request.user)
        elif action == "reject" and acc.status in (Accreditation.PENDING, Accreditation.DRAFT):
            services.reject(acc, request.user, request.POST.get("reason", ""))
        elif action == "cancel" and acc.status != Accreditation.CANCELLED:
            acc.set_status(Accreditation.CANCELLED, request.user)
        elif action == "send" and acc.is_approved and acc.email:
            services.send_ticket(acc)
        elif action == "delete":
            acc.delete()
        else:
            continue
        done += 1
    labels = {"approve": "approved", "reject": "rejected", "cancel": "cancelled",
              "send": "e-mailed", "delete": "deleted"}
    if action in labels:
        if done:
            log(event, f"Bulk {labels[action]} {done} accreditation(s)", request.user)
        messages.success(request, f"{done} accreditation{'s' if done != 1 else ''} {labels[action]}.")
    return safe_next(request, request.get_full_path())


def person_form(request, slug, pk=None):
    event = get_event(slug)
    acc = get_object_or_404(event.accreditations, pk=pk) if pk else None
    initial = {}
    if not acc and request.GET.get("company"):
        initial["company"] = request.GET["company"]
    form = PersonForm(request.POST or None, instance=acc, event=event, initial=initial)
    if not event.accreditation_types.exists():
        messages.warning(request, "Create at least one credential type first.")
        return redirect("types", event.slug)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        if acc:
            person.apply_default_items()
            log(event, f"Edited {person.full_name}", request.user, url=person.get_absolute_url())
            messages.success(request, "Changes saved.")
        else:
            services.approve(person, request.user, notify=form.cleaned_data.get("send_ticket"))
            messages.success(request, f"{person.full_name} added.")
            if "another" in request.POST:
                return redirect("person_create", event.slug)
        return redirect(person)
    return render_event(
        request,
        event,
        "accreditation/person_form.html",
        {"form": form, "person": acc},
        section="people",
    )


def person_detail(request, slug, pk):
    event = get_event(slug)
    acc = get_object_or_404(
        people_queryset(event).prefetch_related("extra_zones", "type__zones"), pk=pk
    )
    if request.method == "POST":
        return person_action(request, acc)
    return render_event(
        request,
        event,
        "accreditation/person_detail.html",
        {
            "person": acc,
            "zones": acc.all_zones(),
            "handouts": acc.items.select_related("item"),
            "available_items": event.items.exclude(handouts__accreditation=acc),
            "scans": acc.scans.select_related("zone", "user")[:20],
            "shifts": acc.shift_assignments.select_related("shift__team", "shift__day"),
            "reject_form": RejectForm(),
        },
        section="people",
    )


def person_action(request, acc):
    action = request.POST.get("action")
    user = request.user
    if action == "approve":
        services.approve(acc, user)
        messages.success(request, f"{acc.full_name} approved" + (" – ticket e-mailed." if acc.email else "."))
    elif action == "reject":
        services.reject(acc, user, request.POST.get("reason", ""))
        messages.info(request, f"{acc.full_name} rejected.")
    elif action == "cancel":
        acc.set_status(Accreditation.CANCELLED, user)
        acc.is_inside = False
        acc.save(update_fields=["is_inside"])
        log(acc.event, f"Cancelled {acc.full_name}", user, url=acc.get_absolute_url())
        messages.info(request, f"{acc.full_name} cancelled.")
    elif action == "restore":
        acc.set_status(Accreditation.PENDING, user)
        messages.info(request, f"{acc.full_name} moved back to pending.")
    elif action == "send":
        if services.send_ticket(acc):
            messages.success(request, f"E-ticket sent to {acc.email}.")
        else:
            messages.error(request, "Only approved accreditations with an e-mail address get a ticket.")
    elif action == "reset_token":
        acc.token = new_token()
        acc.save(update_fields=["token"])
        messages.success(request, "New ticket code generated – the old QR code no longer works.")
    elif action == "item_add":
        item = get_object_or_404(Item, event=acc.event, pk=request.POST.get("item"))
        try:
            qty = max(1, int(request.POST.get("quantity") or 1))
        except ValueError:
            qty = 1
        AccreditationItem.objects.get_or_create(accreditation=acc, item=item, defaults={"quantity": qty})
    elif action == "item_toggle":
        handout = get_object_or_404(acc.items, pk=request.POST.get("handout"))
        handout.issued_at = None if handout.is_issued else timezone.now()
        handout.save(update_fields=["issued_at"])
    elif action == "item_remove":
        acc.items.filter(pk=request.POST.get("handout")).delete()
    elif action == "check_in":
        services.process_scan(acc.event, acc.token, None, Scan.IN, user)
        messages.success(request, f"{acc.full_name} checked in.")
    elif action == "check_out":
        services.process_scan(acc.event, acc.token, None, Scan.OUT, user)
        messages.info(request, f"{acc.full_name} checked out.")
    elif action == "delete":
        acc.delete()
        log(acc.event, f"Deleted {acc.full_name}", user)
        messages.success(request, f"{acc.full_name} deleted.")
        return redirect("people", acc.event.slug)
    return safe_next(request, acc.get_absolute_url())


def approvals(request, slug):
    event = get_event(slug)
    if request.method == "POST":
        return bulk_action(request, event)
    pending = (
        people_queryset(event)
        .filter(status=Accreditation.PENDING)
        .order_by("company__name", "submitted_at")
    )
    groups = {}
    for acc in pending:
        groups.setdefault(acc.company, []).append(acc)
    usage = {c.pk: c.usage() for c in groups if c is not None}
    return render_event(
        request,
        event,
        "accreditation/approvals.html",
        {"groups": groups.items(), "usage": usage, "total": len(pending)},
        section="approvals",
    )


def export_people(request, slug):
    event = get_event(slug)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{slugify(event.name)}-people.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(
        ["first_name", "last_name", "company", "type", "function", "email", "phone",
         "days", "zones", "status", "checked_in", "ticket_url"]
    )
    for acc in people_queryset(event).prefetch_related("extra_zones", "type__zones"):
        writer.writerow(
            [
                acc.first_name,
                acc.last_name,
                acc.company.name if acc.company else "",
                acc.type.name,
                acc.role,
                acc.email,
                acc.phone,
                "; ".join(d.short for d in acc.days.all()) or "All",
                "; ".join(z.name for z in acc.all_zones()),
                acc.get_status_display(),
                timezone.localtime(acc.first_check_in_at).strftime("%Y-%m-%d %H:%M")
                if acc.first_check_in_at
                else "",
                services.absolute(acc.ticket_url()),
            ]
        )
    return response


# ----------------------------------------------------------------- companies


def companies(request, slug):
    event = get_event(slug)
    form = CompanyForm(request.POST or None, event=event, prefix="f-new")
    if request.method == "POST" and form.is_valid():
        company = form.save()
        log(event, f"Company “{company}” added", request.user, url=company.get_absolute_url())
        messages.success(request, f"“{company}” added. Set its contingent below.")
        return redirect(company)
    kind = request.GET.get("kind", "")
    qs = event.companies.annotate(
        n_active=Count("accreditations", filter=~Q(accreditations__status__in=Accreditation.NOT_COUNTED)),
        n_pending=Count("accreditations", filter=Q(accreditations__status=Accreditation.PENDING)),
    ).prefetch_related(Prefetch("contingents"))
    if kind:
        qs = qs.filter(kind=kind)
    rows = [{"company": c, "quota": sum(x.quota for x in c.contingents.all())} for c in qs]
    return render_event(
        request,
        event,
        "accreditation/companies.html",
        {
            "rows": rows,
            "new_form": form,
            "open_dialog": "dlg-new" if form.errors else None,
            "kind": kind,
            "kinds": Company.KINDS,
        },
        section="companies",
    )


def company_detail(request, slug, pk):
    event = get_event(slug)
    company = get_object_or_404(event.companies, pk=pk)
    form = CompanyForm(instance=company, event=event, prefix="company")
    contingents = ContingentForm(company=company, prefix="quota")
    open_dialog = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "edit":
            form = CompanyForm(request.POST, instance=company, event=event, prefix="company")
            if form.is_valid():
                form.save()
                messages.success(request, "Company details saved.")
                return redirect(company)
            open_dialog = "dlg-edit"
        elif action == "contingents":
            contingents = ContingentForm(request.POST, company=company, prefix="quota")
            if contingents.is_valid():
                contingents.save()
                log(event, f"Contingent of {company} updated", request.user, url=company.get_absolute_url())
                messages.success(request, "Contingent saved.")
                return redirect(company)
        elif action == "invite":
            if services.send_portal_invite(company):
                messages.success(request, f"Portal link e-mailed to {company.contact_email}.")
            else:
                messages.error(request, "Add a contact e-mail address first.")
            return redirect(company)
        elif action == "reset_token":
            company.token = new_token()
            company.save(update_fields=["token"])
            messages.success(request, "New portal link generated – the old link no longer works.")
            return redirect(company)
        elif action == "delete":
            if hasattr(company, "artist"):
                messages.error(request, "This company belongs to an artist; delete the artist instead.")
                return redirect(company)
            company.delete()
            messages.success(request, f"“{company}” deleted. Its people were kept without a company.")
            return redirect("companies", event.slug)

    return render_event(
        request,
        event,
        "accreditation/company_detail.html",
        {
            "company": company,
            "form": form,
            "contingents": contingents,
            "usage": company.usage(),
            "people": people_queryset(event).filter(company=company),
            "portal_link": services.absolute(company.portal_url()),
            "open_dialog": open_dialog,
        },
        section="companies",
    )


# ------------------------------------------------------------------- scanner


def scanner(request, slug):
    event = get_event(slug)
    return render_event(
        request,
        event,
        "accreditation/scanner.html",
        {
            "zones": event.zones.all(),
            "recent": event.scans.select_related("accreditation", "zone")[:15],
            "stats": {
                "arrived": event.accreditations.filter(first_check_in_at__isnull=False).count(),
                "inside": event.accreditations.filter(is_inside=True).count(),
                "approved": event.accreditations.filter(status=Accreditation.APPROVED).count(),
            },
        },
        section="scanner",
    )


@require_POST
def scan_api(request, slug):
    event = get_event(slug)
    try:
        data = json.loads(request.body)
    except ValueError:
        data = request.POST
    zone = None
    if data.get("zone"):
        zone = Zone.objects.filter(event=event, pk=data["zone"]).first()
    direction = Scan.OUT if data.get("direction") == Scan.OUT else Scan.IN
    return JsonResponse(services.process_scan(event, data.get("code", ""), zone, direction, request.user))


@require_POST
def handout_api(request, slug, pk):
    event = get_event(slug)
    handout = get_object_or_404(AccreditationItem, pk=pk, accreditation__event=event)
    handout.issued_at = timezone.now()
    handout.save(update_fields=["issued_at"])
    return JsonResponse({"ok": True})


def search_api(request, slug):
    event = get_event(slug)
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        for acc in people_queryset(event).search(q)[:8]:
            results.append(
                {
                    "token": acc.token,
                    "name": acc.full_name,
                    "company": acc.company.name if acc.company else "",
                    "type": acc.type.name,
                    "color": acc.type.color,
                    "status": acc.get_status_display(),
                    "approved": acc.is_approved,
                }
            )
    return JsonResponse({"results": results})
