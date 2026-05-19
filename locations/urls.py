from django.urls import path
from .views import (
    CommuneListCreateView,
    CommuneDetailView,
    QuartierListView,
    LieuStrategiqueView
)

urlpatterns = [
    path('communes/', CommuneListCreateView.as_view(), name='commune-list'),
    path('communes/<int:pk>/', CommuneDetailView.as_view(), name='commune-detail'),
    path('communes/<int:commune_id>/quartiers/', QuartierListView.as_view(), name='quartier-list'),
    path('lieux-strategiques/', LieuStrategiqueView.as_view(), name='lieu-list'),
]