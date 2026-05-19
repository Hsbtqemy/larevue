from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.accounts.views import ReviewerInviteView
from apps.articles.views import ArticleCreateFromJournalView


class ServiceWorkerView(TemplateView):
    template_name = "sw.js"
    content_type = "application/javascript"

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        response["Service-Worker-Allowed"] = "/"
        return response


urlpatterns = [
    path("sw.js", ServiceWorkerView.as_view(), name="sw"),
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),
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
    path("revues/<slug:slug>/inviter/", ReviewerInviteView.as_view(), name="reviewer_invite"),
    path("revues/<slug:slug>/contacts/", include("apps.contacts.urls")),
    path("administration/", include("apps.administration.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
