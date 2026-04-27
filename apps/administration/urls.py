from django.urls import path

from . import views

app_name = "administration"

urlpatterns = [
    path("", views.AdministrationView.as_view(), name="index"),
    path("revues/create/", views.JournalCreateView.as_view(), name="journal_create"),
    path("revues/<slug:slug>/membres/", views.JournalMembersView.as_view(), name="journal_members"),
    path("revues/<slug:slug>/membres/add/", views.JournalMemberAddView.as_view(), name="journal_member_add"),
    path("revues/<slug:slug>/membres/<int:user_id>/remove/", views.JournalMemberRemoveView.as_view(), name="journal_member_remove"),
    path("revues/<slug:slug>/membres/quick-create/", views.JournalMemberQuickCreateView.as_view(), name="journal_member_quick_create"),
    path("utilisateurs/create/", views.UserCreateView.as_view(), name="user_create"),
    path("utilisateurs/search/", views.UserSearchView.as_view(), name="user_search"),
    path("utilisateurs/<int:user_id>/", views.UserDetailView.as_view(), name="user_detail"),
    path("utilisateurs/<int:user_id>/reset-password/", views.UserResetPasswordView.as_view(), name="user_reset_password"),
    path("utilisateurs/<int:user_id>/revues/add/", views.UserAddJournalView.as_view(), name="user_add_journal"),
    path("utilisateurs/<int:user_id>/revues/<slug:slug>/remove/", views.UserRemoveJournalView.as_view(), name="user_remove_journal"),
    path("utilisateurs/<int:user_id>/password/", views.UserPasswordDisplayView.as_view(), name="user_password_display"),
]
