from django.contrib import admin

from .models import PolicePost


@admin.register(PolicePost)
class PolicePostAdmin(admin.ModelAdmin):
    list_display = ("name", "commune", "user", "post_type", "is_active", "updated_at")
    list_filter = ("post_type", "is_active", "commune")
