from django.contrib import admin

from .models import Types, HospitalityEntry, Space, SpaceEntry, RiderEntry

admin.site.register(Types)
admin.site.register(HospitalityEntry)
admin.site.register(Space)
admin.site.register(SpaceEntry)
admin.site.register(RiderEntry)
