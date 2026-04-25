from django.urls import path

from . import views

app_name = "articles"

urlpatterns = [
    path("create/", views.ArticleCreateView.as_view(), name="create"),
    path("<int:article_id>/", views.ArticleDetailView.as_view(), name="detail"),
    path("<int:article_id>/patch/", views.ArticlePatchView.as_view(), name="patch"),
    path("<int:article_id>/edit/", views.ArticleEditView.as_view(), name="edit"),
    path("<int:article_id>/delete/", views.ArticleDeleteView.as_view(), name="delete"),
    path("<int:article_id>/notes/", views.ArticleNoteCreateView.as_view(), name="note_create"),
    # Versions
    path("<int:article_id>/file-upload/", views.ArticleFileUploadView.as_view(), name="file_upload"),
    path("<int:article_id>/versions/<int:version_id>/download/", views.ArticleVersionDownloadView.as_view(), name="version_download"),
    # Relectures
    path("<int:article_id>/reviews/", views.ReviewRequestCreateView.as_view(), name="review_create"),
    path("<int:article_id>/reviews/<int:review_id>/send/", views.ReviewRequestSendView.as_view(), name="review_send"),
    path("<int:article_id>/reviews/<int:review_id>/decline/", views.ReviewRequestDeclineView.as_view(), name="review_decline"),
    path("<int:article_id>/reviews/<int:review_id>/receive/", views.ReviewRequestReceiveView.as_view(), name="review_receive"),
    path("<int:article_id>/reviews/<int:review_id>/delete/", views.ReviewRequestDeleteView.as_view(), name="review_delete"),
    path("<int:article_id>/reviews/<int:review_id>/download/", views.ReviewRequestFileDownloadView.as_view(), name="review_download"),
    path("<int:article_id>/reviews/<int:review_id>/patch/", views.ReviewRequestPatchView.as_view(), name="review_patch"),
    path("<int:article_id>/transition/", views.ArticleTransitionView.as_view(), name="transition"),
]
