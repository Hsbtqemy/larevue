from django.urls import path

from . import views

app_name = "issues"

urlpatterns = [
    path("<int:issue_id>/", views.IssueDetailView.as_view(), name="detail"),
    path("<int:issue_id>/patch/", views.IssuePatchView.as_view(), name="patch"),
    path("<int:issue_id>/cover/", views.IssueImageUploadView.as_view(), name="cover"),
    path("<int:issue_id>/edit/", views.IssueEditView.as_view(), name="edit"),
    path("<int:issue_id>/delete/", views.IssueDeleteView.as_view(), name="delete"),
]
