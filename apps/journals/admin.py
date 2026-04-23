from django.contrib import admin

from .models import Journal, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 1
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at"]
    fields = ["user", "created_at"]


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "accent_color", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [MembershipInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description")}),
        ("Apparence", {"fields": ("logo", "accent_color")}),
        ("Métadonnées", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "journal", "created_at")
    list_filter = ("journal",)
    search_fields = ("user__email", "user__first_name", "user__last_name", "journal__name")
    readonly_fields = ("created_at",)
    autocomplete_fields = ["user", "journal"]
