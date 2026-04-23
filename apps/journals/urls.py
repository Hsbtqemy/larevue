from django.urls import path

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("revues/<slug:slug>/", views.JournalDashboardView.as_view(), name="journal_dashboard"),
]
