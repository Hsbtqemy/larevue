from django.contrib import admin
from django_fsm.admin import FSMAdminMixin

from .models import Issue, IssueDocument


@admin.register(Issue)
class IssueAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ["state"]
    list_display = (
        "number",
        "thematic_title",
        "journal",
        "state",
        "editor_name",
        "planned_publication_date",
        "get_progress",
    )
    list_filter = ("journal", "state")
    search_fields = ("number", "thematic_title", "editor_name")
    readonly_fields = ("created_at", "updated_at", "state", "get_progress")
    autocomplete_fields = ["journal"]
    fieldsets = (
        (None, {"fields": ("journal", "number", "thematic_title", "description")}),
        (
            "Responsable et calendrier",
            {"fields": ("editor_name", "planned_publication_date")},
        ),
        ("Médias", {"fields": ("cover_image", "final_pdf")}),
        ("Workflow", {"fields": ("state", "get_progress")}),
        ("Métadonnées", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Avancement")
    def get_progress(self, obj):
        return f"{obj.progress} %"


@admin.register(IssueDocument)
class IssueDocumentAdmin(admin.ModelAdmin):
    list_display = ("name", "issue", "uploaded_by", "uploaded_at")
    list_filter = ("issue__journal",)
    search_fields = ("name", "issue__thematic_title")
    readonly_fields = ("uploaded_at", "uploaded_by")
