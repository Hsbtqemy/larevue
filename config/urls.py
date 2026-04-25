from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.articles.views import ArticleCreateFromJournalView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.journals.urls")),
    path("revues/<slug:slug>/numeros/", include("apps.issues.urls")),
    path("revues/<slug:slug>/numeros/<int:issue_id>/articles/", include("apps.articles.urls")),
    path(
        "revues/<slug:slug>/articles/create/",
        ArticleCreateFromJournalView.as_view(),
        name="article_create_from_journal",
    ),
    path("revues/<slug:slug>/contacts/", include("apps.contacts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
