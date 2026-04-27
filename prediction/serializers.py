from rest_framework import serializers

class DangerPredictionSerializer(serializers.Serializer):
    latitude_report = serializers.FloatField()
    longitude_report = serializers.FloatField()
    prediction = serializers.IntegerField()
