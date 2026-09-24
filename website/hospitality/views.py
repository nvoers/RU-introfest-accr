from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import HospitalityTypeForm
from .models import Types


def hospitality_list(request):
    bound = {}
    open_dialog = None

    if request.method == "POST":
        item = None
        if request.POST.get("item"):
            item = get_object_or_404(Types, pk=request.POST["item"])
        if request.POST.get("action") == "delete" and item is not None:
            item.delete()
            messages.success(request, f"“{item.name}” deleted.")
            return redirect("hospitality_list")

        key = item.pk if item else "new"
        form = HospitalityTypeForm(request.POST, instance=item, prefix=f"type-{key}")
        if form.is_valid():
            saved = form.save()
            messages.success(
                request, f"“{saved.name}” {'updated' if item else 'added'}."
            )
            return redirect("hospitality_list")
        bound[key] = form
        open_dialog = f"dlg-type-{key}"

    rows = [
        {
            "item": item,
            "form": bound.get(item.pk)
            or HospitalityTypeForm(instance=item, prefix=f"type-{item.pk}"),
        }
        for item in Types.objects.annotate(usage=Count("allocations"))
    ]
    return render(
        request,
        "hospitality/hospitality_list.html",
        {
            "rows": rows,
            "new_form": bound.get("new") or HospitalityTypeForm(prefix="type-new"),
            "open_dialog": open_dialog,
        },
    )
