from rest_framework import serializers
from .models import Commune, Quartier, LieuStrategique

class CommuneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commune
        fields = '__all__'

class QuartierSerializer(serializers.ModelSerializer):
    commune_nom = serializers.CharField(source='commune.nom', read_only=True)
    
    class Meta:
        model = Quartier
        fields = '__all__'
        extra_kwargs = {
            'limites_gps': {'write_only': True}  # Masqué en sortie pour sécurité
        }

class LieuStrategiqueSerializer(serializers.ModelSerializer):
    quartier_info = serializers.SerializerMethodField()
    
    class Meta:
        model = LieuStrategique
        fields = '__all__'
    
    def get_quartier_info(self, obj):
        return {
            'id': obj.quartier.id,
            'nom': obj.quartier.nom,
            'commune': obj.quartier.commune.nom
        }