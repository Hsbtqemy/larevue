from django.urls import path

from . import views

app_name = "issues"

urlpatterns = [
    path("", views.IssueListView.as_view(), name="list"),
    path("create/", views.IssueCreateView.as_view(), name="create"),
    path("<int:issue_id>/", views.IssueDetailView.as_view(), name="detail"),
    path("<int:issue_id>/patch/", views.IssuePatchView.as_view(), name="patch"),
    path("<int:issue_id>/cover/", views.IssueImageUploadView.as_view(), name="cover"),
    path("<int:issue_id>/edit/", views.IssueEditView.as_view(), name="edit"),
    path("<int:issue_id>/delete/", views.IssueDeleteView.as_view(), name="delete"),
    path("<int:issue_id>/transition/", views.IssueTransitionView.as_view(), name="transition"),
    path("<int:issue_id>/documents/create/", views.IssueDocumentCreateView.as_view(), name="document_create"),
    path("<int:issue_id>/documents/<int:doc_id>/delete/", views.IssueDocumentDeleteView.as_view(), name="document_delete"),
    path("<int:issue_id>/documents/<int:doc_id>/download/", views.IssueDocumentDownloadView.as_view(), name="document_download"),
]
