from django.contrib import admin
from django_fsm.admin import FSMAdminMixin

from .models import Article, ArticleVersion, InternalNote


class ArticleVersionInline(admin.TabularInline):
    model = ArticleVersion
    extra = 0
    readonly_fields = ("version_number", "uploaded_by", "created_at")
    fields = ("version_number", "file", "comment", "uploaded_by", "created_at")


class InternalNoteInline(admin.TabularInline):
    model = InternalNote
    extra = 0
    readonly_fields = ("author", "is_automatic", "created_at")
    fields = ("content", "author", "is_automatic", "created_at")


@admin.register(Article)
class ArticleAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ["state"]
    list_display = ("title", "issue", "get_author", "article_type", "state", "order")
    list_filter = ("issue__journal", "article_type", "state")
    search_fields = ("title", "author__first_name", "author__last_name")
    readonly_fields = ("created_at", "updated_at", "state")
    autocomplete_fields = ["issue", "author"]
    inlines = [ArticleVersionInline, InternalNoteInline]
    fieldsets = (
        (None, {"fields": ("issue", "title", "article_type", "order")}),
        ("Auteur·ice", {"fields": ("author", "author_name_override")}),
        ("Workflow", {"fields": ("state",)}),
        ("Métadonnées", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Auteur·ice")
    def get_author(self, obj):
        return obj.displayed_author_name or "—"


@admin.register(ArticleVersion)
class ArticleVersionAdmin(admin.ModelAdmin):
    list_display = ("article", "version_number", "uploaded_by", "created_at")
    list_filter = ("article__issue__journal",)
    search_fields = ("article__title",)
    readonly_fields = ("version_number", "created_at", "updated_at")
    autocomplete_fields = ["article"]


@admin.register(InternalNote)
class InternalNoteAdmin(admin.ModelAdmin):
    list_display = ("article", "author", "is_automatic", "created_at")
    list_filter = ("is_automatic", "article__issue__journal")
    search_fields = ("article__title", "content")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ["article"]
