# Generated by Django 5.2 on 2025-06-12 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plataforma', '0030_remove_clase_fecha_clase'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='rol',
            field=models.CharField(choices=[('alumno', 'Alumno'), ('profesor', 'Profesor'), ('tutor', 'Tutor')], default='alumno', max_length=20),
        ),
    ]
