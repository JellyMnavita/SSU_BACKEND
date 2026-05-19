from rest_framework import serializers

class ScrappingSerializer(serializers.Serializer):
    title = serializers.CharField()
    link = serializers.URLField()
    image = serializers.URLField(allow_null=True)
    date = serializers.CharField() 