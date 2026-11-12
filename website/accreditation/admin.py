from django.contrib import admin

from .models import Accreditation, AccreditationItem, AccreditationType, Company, Contingent, Item, Scan, Zone

admin.site.register([Zone, Item, AccreditationType])


class ContingentInline(admin.TabularInline):
    model = Contingent
    extra = 0


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "event", "contact_email"]
    list_filter = ["event", "kind"]
    inlines = [ContingentInline]


class ItemInline(admin.TabularInline):
    model = AccreditationItem
    extra = 0


@admin.register(Accreditation)
class AccreditationAdmin(admin.ModelAdmin):
    list_display = ["full_name", "company", "type", "status", "event"]
    list_filter = ["event", "status", "type"]
    search_fields = ["first_name", "last_name", "email"]
    inlines = [ItemInline]


@admin.register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ["created_at", "accreditation", "zone", "direction", "result", "message"]
    list_filter = ["event", "result"]
