from django.contrib import admin

from .models import Artist, HotelRoom, Performance, Stage, Transport

admin.site.register([Stage, Performance, Transport, HotelRoom])


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ["name", "event", "advancing_status"]
    list_filter = ["event", "advancing_status"]
