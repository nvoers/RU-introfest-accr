from django.contrib import admin

from .models import HospitalityEntry, RiderEntry, Space, SpaceEntry, Types


@admin.register(Types)
class TypesAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "value"]
    list_filter = ["type"]


@admin.register(HospitalityEntry)
class HospitalityEntryAdmin(admin.ModelAdmin):
    list_display = ["entry", "type", "amount", "status"]
    list_filter = ["status", "type", "entry__event"]


@admin.register(Space)
class SpaceAdmin(admin.ModelAdmin):
    list_display = ["name", "event"]
    list_filter = ["event"]


admin.site.register(SpaceEntry)
admin.site.register(RiderEntry)
