from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("create/", views.ContactCreateView.as_view(), name="create"),
]
