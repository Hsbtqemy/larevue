from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profil/", views.ProfileView.as_view(), name="profile"),
    path("profil/relectures/", views.MesRelecturesView.as_view(), name="mes_relectures"),
    path("profil/patch/", views.ProfilePatchView.as_view(), name="profile_patch"),
    path("profil/password/", views.ProfilePasswordView.as_view(), name="profile_password"),
    path("inviter/<str:token>/activer/", views.ReviewerActivateView.as_view(), name="reviewer_activate"),
    path("reviewer/", views.ReviewerDashboardView.as_view(), name="reviewer_dashboard"),
    path("relecture/<int:pk>/fichier/", views.ReviewerArticleDownloadView.as_view(), name="reviewer_article_download"),
    path("relecture/<int:pk>/deposer/", views.ReviewerReviewSubmitView.as_view(), name="reviewer_review_submit"),
]
