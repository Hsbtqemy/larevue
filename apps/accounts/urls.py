from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profil/", views.ProfileView.as_view(), name="profile"),
    path("profil/patch/", views.ProfilePatchView.as_view(), name="profile_patch"),
    path("profil/password/", views.ProfilePasswordView.as_view(), name="profile_password"),
]
