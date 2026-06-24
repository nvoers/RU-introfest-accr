from django.views.generic import ListView, TemplateView, RedirectView
from django.shortcuts import render, redirect
from django.http import HttpResponse
from accreditatie.models import Event, Entrance, AccessLevel, AccessEntry
