from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.ContactListView.as_view(), name="list"),
    path("create/", views.ContactCreateView.as_view(), name="create"),
    path("search/", views.ContactSearchAPIView.as_view(), name="search"),
    path("<int:pk>/", views.ContactDetailView.as_view(), name="detail"),
    path("<int:pk>/patch/", views.ContactPatchView.as_view(), name="patch"),
    path("<int:pk>/edit/", views.ContactEditView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ContactDeleteView.as_view(), name="delete"),
]
