# Generated by Django 5.2 on 2025-06-06 23:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plataforma', '0010_alter_curso_duracion'),
    ]

    operations = [
        migrations.AddField(
            model_name='curso',
            name='icono1',
            field=models.ImageField(blank=True, null=True, upload_to='fotos_perfil/'),
        ),
    ]
