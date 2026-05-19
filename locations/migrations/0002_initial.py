from django.db import migrations

def load_communes(apps, schema_editor):
    Commune = apps.get_model('locations', 'Commune')
    
    COMMUNES_DATA = [
        {
            'nom': 'Bandalungwa',
            'superficie': 6.82,
            'population': 202341,
            'maire': 'À compléter',
            'contact_urgence': '+243810000001',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Barumbu',
            'superficie': 4.72,
            'population': 150319,
            'maire': 'À compléter',
            'contact_urgence': '+243810000002',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Bumbu',
            'superficie': 5.30,
            'population': 329234,
            'maire': 'À compléter',
            'contact_urgence': '+243810000003',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Gombe',
            'superficie': 29.33,
            'population': 32373,
            'maire': 'À compléter',
            'contact_urgence': '+243810000004',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Kalamu',
            'superficie': 6.64,
            'population': 315342,
            'maire': 'À compléter',
            'contact_urgence': '+243810000005',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Kasa-Vubu',
            'superficie': 5.05,
            'population': 157320,
            'maire': 'À compléter',
            'contact_urgence': '+243810000006',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Kimbanseke',
            'superficie': 237.78,
            'population': 946372,
            'maire': 'À compléter',
            'contact_urgence': '+243810000007',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Kinshasa',
            'superficie': 2.87,
            'population': 164857,
            'maire': 'À compléter',
            'contact_urgence': '+243810000008',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Kintambo',
            'superficie': 2.72,
            'population': 106772,
            'maire': 'À compléter',
            'contact_urgence': '+243810000009',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Kisenso',
            'superficie': 16.60,
            'population': 386151,
            'maire': 'À compléter',
            'contact_urgence': '+243810000010',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Lemba',
            'superficie': 23.70,
            'population': 349838,
            'maire': 'À compléter',
            'contact_urgence': '+243810000011',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Limete',
            'superficie': 67.60,
            'population': 375726,
            'maire': 'À compléter',
            'contact_urgence': '+243810000012',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Lingwala',
            'superficie': 2.88,
            'population': 94635,
            'maire': 'À compléter',
            'contact_urgence': '+243810000013',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Makala',
            'superficie': 5.60,
            'population': 253844,
            'maire': 'À compléter',
            'contact_urgence': '+243810000014',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Maluku',
            'superficie': 7948.80,
            'population': 179648,
            'maire': 'À compléter',
            'contact_urgence': '+243810000015',
            'date_creation': '2003-01-01'
        },
        {
            'nom': 'Masina',
            'superficie': 69.93,
            'population': 485167,
            'maire': 'À compléter',
            'contact_urgence': '+243810000016',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Matete',
            'superficie': 4.88,
            'population': 268781,
            'maire': 'À compléter',
            'contact_urgence': '+243810000017',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Mont-Ngafula',
            'superficie': 358.92,
            'population': 261004,
            'maire': 'À compléter',
            'contact_urgence': '+243810000018',
            'date_creation': '2003-01-01'
        },
        {
            'nom': 'Ndjili',
            'superficie': 11.40,
            'population': 442138,
            'maire': 'À compléter',
            'contact_urgence': '+243810000019',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Ngaba',
            'superficie': 4.00,
            'population': 180650,
            'maire': 'À compléter',
            'contact_urgence': '+243810000020',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Ngaliema',
            'superficie': 224.30,
            'population': 683135,
            'maire': 'À compléter',
            'contact_urgence': '+243810000021',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Ngiri-Ngiri',
            'superficie': 3.40,
            'population': 174843,
            'maire': 'À compléter',
            'contact_urgence': '+243810000022',
            'date_creation': '1968-01-01'
        },
        {
            'nom': 'Nsele',
            'superficie': 898.79,
            'population': 140929,
            'maire': 'À compléter',
            'contact_urgence': '+243810000023',
            'date_creation': '2003-01-01'
        },
        {
            'nom': 'Selembao',
            'superficie': 23.18,
            'population': 335581,
            'maire': 'À compléter',
            'contact_urgence': '+243810000024',
            'date_creation': '1968-01-01'
        }
    ]
    
    for commune in COMMUNES_DATA:
        Commune.objects.get_or_create(
            nom=commune['nom'],
            defaults=commune
        )

class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0001_initial'),  # Dépend de votre migration initiale
    ]

    operations = [
        migrations.RunPython(load_communes),
    ]