from django.urls import path
from .views import DangerPredictionProximityAPIView
from .views import DangerPredictSingleAPIView


urlpatterns = [
    path('danger-predictions/', DangerPredictionProximityAPIView.as_view()),
    path('danger-predict-single/', DangerPredictSingleAPIView.as_view()),
]