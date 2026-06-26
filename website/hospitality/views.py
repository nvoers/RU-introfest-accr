from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from .models import Types
from .forms import NewHospitalityTypeForm


class HospitalityListView(TemplateView):
    template_name = "hospitality/hospitality_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hospitality_types = Types.objects.all()
        context["hospitality_types"] = hospitality_types
        context["form"] = NewHospitalityTypeForm()
        return context

    def post(self, request, *args, **kwargs):
        form = NewHospitalityTypeForm(request.POST)
        hospitality_types = Types.objects.all()

        if form.is_valid():
            value = form.cleaned_data["value"]
            if value in (None, ""):
                value = 1 if form.cleaned_data["type"] == Types.COIN else 0

            hospitality_type = Types(
                name=form.cleaned_data["name"],
                type=form.cleaned_data["type"],
                value=value,
            )
            hospitality_type.full_clean()
            hospitality_type.save()
            return redirect("hospitality_list")

        context = {
            "hospitality_types": hospitality_types,
            "form": form,
        }
        return render(request, self.template_name, context)
