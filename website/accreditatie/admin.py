from django.contrib import admin

from hospitality.models import HospitalityEntry, RiderEntry, SpaceEntry

from .models import AccessEntry, AccessLevel, Entrance, Event


class EventScopedAdmin(admin.ModelAdmin):
    list_display = ["name", "event"]
    list_filter = ["event"]
    search_fields = ["name"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "start_time", "end_time", "location"]
    search_fields = ["name", "location"]
    date_hierarchy = "date"


@admin.register(AccessLevel)
class AccessLevelAdmin(EventScopedAdmin):
    list_display = ["name", "color", "event"]


admin.site.register(Entrance, EventScopedAdmin)


class SpaceEntryInline(admin.TabularInline):
    model = SpaceEntry
    extra = 0


class HospitalityEntryInline(admin.TabularInline):
    model = HospitalityEntry
    extra = 0


class RiderEntryInline(admin.TabularInline):
    model = RiderEntry
    extra = 0


@admin.register(AccessEntry)
class AccessEntryAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "organisation",
        "event",
        "access_type",
        "number_of_tickets",
        "access_level",
        "status",
    ]
    list_filter = ["event", "status", "access_type", "access_level"]
    search_fields = ["name", "organisation", "email"]
    readonly_fields = ["checked_in_at", "created_at", "updated_at"]
    inlines = [SpaceEntryInline, HospitalityEntryInline, RiderEntryInline]
