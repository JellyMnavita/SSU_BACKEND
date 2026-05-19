from django.urls import path
from .views import GetScrappingView

urlpatterns = [
    path('articles/', GetScrappingView.as_view(), name='articles'),
] 