from django.contrib import admin

from .models import ReviewRequest


@admin.register(ReviewRequest)
class ReviewRequestAdmin(admin.ModelAdmin):
    list_display = (
        "article",
        "reviewer_name_snapshot",
        "deadline",
        "state",
        "verdict",
        "get_is_overdue",
    )
    list_filter = ("state", "verdict", "article__issue__journal")
    search_fields = ("reviewer_name_snapshot", "article__title")
    readonly_fields = ("created_at", "updated_at", "reviewer_name_snapshot", "get_is_overdue")
    autocomplete_fields = ["article", "article_version", "reviewer"]
    fieldsets = (
        (None, {"fields": ("article", "article_version")}),
        ("Relecteur·ice", {"fields": ("reviewer", "reviewer_name_snapshot")}),
        ("Calendrier et état", {"fields": ("deadline", "state", "get_is_overdue")}),
        (
            "Retour de relecture",
            {"fields": ("received_file", "received_at", "verdict", "internal_notes")},
        ),
        ("Métadonnées", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="En retard ?", boolean=True)
    def get_is_overdue(self, obj):
        return obj.is_overdue
