from django.urls import path

from . import views

app_name = "articles"

urlpatterns = [
    path("<int:article_id>/", views.ArticleDetailView.as_view(), name="detail"),
    path("<int:article_id>/patch/", views.ArticlePatchView.as_view(), name="patch"),
    path("<int:article_id>/edit/", views.ArticleEditView.as_view(), name="edit"),
    path("<int:article_id>/delete/", views.ArticleDeleteView.as_view(), name="delete"),
    path("<int:article_id>/notes/", views.ArticleNoteCreateView.as_view(), name="note_create"),
]
