from django.contrib import admin

from .models import CrewSettings, Shift, ShiftAssignment, Team, VolunteerProfile

admin.site.register([Team, ShiftAssignment, VolunteerProfile, CrewSettings])


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ["team", "day", "start", "end", "capacity"]
    list_filter = ["team__event", "team"]
