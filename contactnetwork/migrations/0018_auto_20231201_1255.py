# Generated by Django 3.2.18 on 2023-12-01 11:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contactnetwork', '0017_auto_20231130_1403'),
    ]

    operations = [
        migrations.AlterField(
            model_name='interactingpeptideresiduepair',
            name='ca_cb_ca_angle',
            field=models.CharField(max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='interactingpeptideresiduepair',
            name='ca_distance',
            field=models.CharField(max_length=10, null=True),
        ),
    ]
