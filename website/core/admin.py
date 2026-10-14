from django.contrib import admin

from .models import Activity, Event, EventDay


class DayInline(admin.TabularInline):
    model = EventDay
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "venue"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [DayInline]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["created_at", "event", "text", "who"]
    list_filter = ["event"]
