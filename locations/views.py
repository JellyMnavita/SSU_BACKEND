from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Commune, Quartier, LieuStrategique
from .serializers import CommuneSerializer, QuartierSerializer, LieuStrategiqueSerializer

class CommuneListCreateView(generics.ListCreateAPIView):
    queryset = Commune.objects.all()
    serializer_class = CommuneSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom']

class CommuneDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Commune.objects.all()
    serializer_class = CommuneSerializer

class QuartierListView(generics.ListCreateAPIView):
    serializer_class = QuartierSerializer
    def get_queryset(self):
        commune_id = self.kwargs.get('commune_id')
        return Quartier.objects.filter(commune_id=commune_id)

class LieuStrategiqueView(generics.ListCreateAPIView):
    serializer_class = LieuStrategiqueSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'quartier']
    search_fields = ['nom', 'adresse']

    def get_queryset(self):
        queryset = LieuStrategique.objects.all()
        
        # Filtre par distance si coordonnées fournies
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        radius = self.request.query_params.get('radius', 5)  # 5km par défaut
        
        if lat and lng:
            queryset = queryset.extra(
                where=[f"""
                ST_Distance(
                    ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 3857),
                    ST_Transform(ST_SetSRID(ST_MakePoint(%s, %s), 4326), 3857)
                ) / 1000 <= %s
                """],
                params=[lng, lat, float(radius)]
            )
        
        return queryset