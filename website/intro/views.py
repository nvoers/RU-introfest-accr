from django.views.generic import TemplateView, RedirectView
from django.shortcuts import render, redirect
from django.http import HttpResponse


class IndexView(TemplateView):
    """Index view."""

    template_name = "intro/index.html"
