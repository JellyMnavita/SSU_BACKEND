from django.contrib import admin

from .models import CompanySite


@admin.register(CompanySite)
class CompanySiteAdmin(admin.ModelAdmin):
    list_display = ("name", "commune", "user", "site_type", "is_planned", "alert_radius_m")
    list_filter = ("site_type", "is_planned", "commune")
    search_fields = ("name", "commune", "user__username")
