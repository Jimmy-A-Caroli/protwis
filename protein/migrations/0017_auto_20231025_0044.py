# Generated by Django 3.0.3 on 2023-10-24 22:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('protein', '0016_auto_20220225_1650'),
    ]

    operations = [
        migrations.CreateModel(
            name='Biosensor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('downstream_steps', models.IntegerField()),
                ('parameter', models.TextField()),
            ],
            options={
                'db_table': 'protein_couplings_biosensor',
            },
        ),
        migrations.RenameField(
            model_name='proteincouplings',
            old_name='emax',
            new_name='logemaxec50',
        ),
        migrations.RemoveField(
            model_name='proteincouplings',
            name='logmaxec50',
        ),
        migrations.RemoveField(
            model_name='proteincouplings',
            name='pec50',
        ),
        migrations.RemoveField(
            model_name='proteincouplings',
            name='stand_dev',
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='deltaGDP_conc',
            field=models.DecimalField(decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='deltaGDP_conc_family',
            field=models.DecimalField(decimal_places=1, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='family_rank',
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='kon_mean',
            field=models.DecimalField(decimal_places=1, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='kon_mean_family',
            field=models.DecimalField(decimal_places=1, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='logemaxec50_family',
            field=models.DecimalField(decimal_places=1, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='other_protein',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='percent_of_primary_family',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='percent_of_primary_subtype',
            field=models.IntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='proteincouplings',
            name='physiological_ligand',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AddField(
            model_name='proteincouplings',
            name='biosensor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='protein.Biosensor'),
        ),
    ]
