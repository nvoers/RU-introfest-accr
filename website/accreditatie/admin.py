from django.contrib import admin

from .models import Event, AccessEntry, Entrance, AccessLevel

admin.site.register(AccessEntry)
admin.site.register(Event)
admin.site.register(Entrance)
admin.site.register(AccessLevel)
