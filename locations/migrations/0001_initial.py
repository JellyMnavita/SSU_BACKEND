import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Commune',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100, unique=True)),
                ('superficie', models.FloatField(help_text='En km²')),
                ('population', models.PositiveIntegerField()),
                ('maire', models.CharField(max_length=100)),
                ('contact_urgence', models.CharField(max_length=20)),
                ('date_creation', models.DateField()),
            ],
            options={
                'verbose_name': 'Commune',
                'verbose_name_plural': 'Communes',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='Quartier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('limites_gps', models.TextField(help_text='Coordonnées JSON des limites du quartier')),
                ('points_interet', models.JSONField(default=list, help_text='Hôpitaux, commissariats, etc.')),
                ('taux_criminalite', models.FloatField(default=0.0)),
                ('commune', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='quartiers', to='locations.commune')),
            ],
            options={
                'verbose_name': 'Quartier',
                'ordering': ['commune__nom', 'nom'],
                'unique_together': {('commune', 'nom')},
            },
        ),
        migrations.CreateModel(
            name='LieuStrategique',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('POLICE', 'Commissariat'), ('HOPITAL', 'Hôpital'), ('CASERNE', 'Caserne militaire'), ('MARCHE', 'Marché')], max_length=20)),
                ('nom', models.CharField(max_length=200)),
                ('adresse', models.TextField()),
                ('longitude', models.FloatField()),
                ('latitude', models.FloatField()),
                ('contact', models.CharField(max_length=20)),
                ('responsable', models.CharField(max_length=100)),
                ('quartier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='locations.quartier')),
            ],
            options={
                'verbose_name': 'Lieu stratégique',
                'ordering': ['quartier', 'type'],
            },
        ),
    ]
