# Generated by Django 5.2 on 2025-06-09 20:32

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plataforma', '0020_alter_clase_curso'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clase',
            name='id',
        ),
        migrations.AddField(
            model_name='clase',
            name='id_clase',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.CreateModel(
            name='ClaseComision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(blank=True, null=True)),
                ('horario', models.TimeField(blank=True, null=True)),
                ('link', models.URLField(blank=True, null=True)),
                ('video', models.URLField(blank=True, null=True)),
                ('clase', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instancias', to='plataforma.clase')),
                ('comision', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clases', to='plataforma.comision')),
            ],
        ),
    ]
