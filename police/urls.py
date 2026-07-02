from django.urls import path

from .views import (
    PoliceDashboardView,
    PolicePostDetailView,
    PolicePostListCreateView,
    PolicePostPublicListView,
)

urlpatterns = [
    path("police/dashboard/", PoliceDashboardView.as_view(), name="police-dashboard"),
    path("police/posts/public/", PolicePostPublicListView.as_view(), name="police-posts-public"),
    path("police/posts/", PolicePostListCreateView.as_view(), name="police-posts"),
    path("police/posts/<int:pk>/", PolicePostDetailView.as_view(), name="police-post-detail"),
]
