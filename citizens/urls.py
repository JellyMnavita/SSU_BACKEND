from django.urls import path

from .views import CitizenListView

urlpatterns = [
    path("admin/citizens/", CitizenListView.as_view(), name="citizen-list"),
]

