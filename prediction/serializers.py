from rest_framework import serializers

class DangerPredictionSerializer(serializers.Serializer):
    latitude_report = serializers.FloatField()
    longitude_report = serializers.FloatField()
    prediction = serializers.IntegerField()



class RouteCoordinateSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class RouteCandidateSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=False)
    distance_m = serializers.FloatField(min_value=0)
    duration_s = serializers.FloatField(min_value=0)
    geometry = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(),
            min_length=2,
            max_length=2,
        ),
        min_length=2,
    )


class SafeRouteRequestSerializer(serializers.Serializer):
    origin = RouteCoordinateSerializer()
    destination = RouteCoordinateSerializer()
    hour = serializers.IntegerField(min_value=0, max_value=23, required=False)
    day_of_week = serializers.IntegerField(min_value=0, max_value=6, required=False)
    routes = serializers.ListField(
        child=RouteCandidateSerializer(),
        min_length=1,
        max_length=10,
    )
