# Generated by Django 5.2 on 2025-06-08 23:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plataforma', '0017_alter_curso_duracion'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clase',
            name='comision',
        ),
    ]
