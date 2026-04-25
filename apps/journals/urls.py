from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("revues/<slug:slug>/", views.JournalDashboardView.as_view(), name="journal_dashboard"),
    path("revues/<slug:slug>/modifier/", views.JournalEditView.as_view(), name="journal_edit"),
    path("revues/<slug:slug>/documents/create/", views.JournalDocumentCreateView.as_view(), name="journal_document_create"),
    path("revues/<slug:slug>/documents/<int:doc_id>/delete/", views.JournalDocumentDeleteView.as_view(), name="journal_document_delete"),
    path("revues/<slug:slug>/documents/<int:doc_id>/download/", views.JournalDocumentDownloadView.as_view(), name="journal_document_download"),
]
