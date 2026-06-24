from django.views.generic import TemplateView, RedirectView
from django.shortcuts import render, redirect
from django.http import HttpResponse


def index(request):
    return render(request, "intro/index.html")
