from django.contrib import admin

from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "affiliation", "journal", "get_roles")
    list_filter = ("journal",)
    search_fields = ("first_name", "last_name", "email", "affiliation")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["journal"]
    fieldsets = (
        (None, {"fields": ("journal", "first_name", "last_name", "email", "affiliation")}),
        ("Rôles et notes", {"fields": ("usual_roles", "notes")}),
        ("Métadonnées", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Rôles")
    def get_roles(self, obj):
        return ", ".join(obj.usual_roles) if obj.usual_roles else "—"
