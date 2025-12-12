# plataforma/management/commands/enviar_newsletter.py

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime

from plataforma.models import Suscriptor, DatosDeEstudiantes, PerfilUsuario


class Command(BaseCommand):
    help = 'Envía la newsletter con el diseño oscuro + verde neón que te encanta'

    def add_arguments(self, parser):
        parser.add_argument('--numero-edicion', type=str, required=True, help='Ej: #47')
        parser.add_argument('--titulo-novedad', type=str, required=True, help='Título de la novedad destacada')
        parser.add_argument('--extracto-novedad', type=str, required=True, help='Párrafo corto de la novedad')
        parser.add_argument('--link-novedad', type=str, required=True, help='URL del artículo o video')
        parser.add_argument('--titulo-promocion', type=str, required=True, help='Ej: 40% OFF en todos los cursos')
        parser.add_argument('--descuento', type=str, default='40%', help='Ej: 40%')
        parser.add_argument('--codigo-cupon', type=str, required=True, help='Código del cupón')
        parser.add_argument('--fecha-vencimiento', type=str, required=True, help='Ej: 20 de enero')
        parser.add_argument('--link-promocion', type=str, required=True, help='URL de la promo')
        parser.add_argument('--dry-run', action='store_true', help='Solo prueba')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Día de la semana en español
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        dia_semana = dias[timezone.now().weekday()]

        # Todos los correos únicos
        emails_suscriptores = Suscriptor.objects.values_list('email', flat=True)
        emails_alumnos = PerfilUsuario.objects.filter(rol='alumno').values_list('correo', flat=True)
        todos_emails = set(list(emails_suscriptores) + list(emails_alumnos))

        total = len(todos_emails)
        self.stdout.write(f"Enviando newsletter a {total} contactos...")

        enviados = 0
        for email in todos_emails:
            if not email:
                continue

            # Nombre personalizado
            nombre = "amigo/a"
            try:
                perfil = PerfilUsuario.objects.get(correo__iexact=email)
                if perfil.id_estudiante:
                    nombre = perfil.id_estudiante.nombre.split()[0]
            except:
                pass

            context = {
                'nombre': nombre,
                'dia_semana': dia_semana,
                'numero_edicion': options['numero_edicion'],
                'titulo_novedad': options['titulo_novedad'],
                'extracto_novedad': options['extracto_novedad'],
                'link_novedad': options['link_novedad'],
                'titulo_promocion': options['titulo_promocion'],
                'descuento': options['descuento'],
                'codigo_cupon': options['codigo_cupon'],
                'fecha_vencimiento': options['fecha_vencimiento'],
                'link_promocion': options['link_promocion'],
                'link_discord': "https://discord.gg/tecnomarema",
                'link_linkedin': "https://linkedin.com/company/tecnomarema",
                'link_youtube': "https://youtube.com/@tecnomarema",
                'link_instagram': "https://instagram.com/tecnomarema",
                'link_facebook': "https://facebook.com/tecnomarema",
                'link_unsubscribe': f"https://tudominio.com/unsubscribe/?email={email}",
            }

            html_message = render_to_string('registration/newsletter.html', context)

            if dry_run:
                self.stdout.write(self.style.NOTICE(f"[PRUEBA] → {email}"))
            else:
                try:
                    send_mail(
                        subject=f"{dia_semana}: {options['titulo_promocion']} + Novedades Tecno Marema",
                        message="",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email.strip().lower()],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    self.stdout.write(self.style.SUCCESS(f"Enviado → {email}"))
                    enviados += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error → {email}: {e}"))

        resumen = f"Newsletter #{options['numero_edicion']} enviada a {enviados}/{total} contactos"
        if dry_run:
            resumen += " (modo prueba)"
        self.stdout.write(self.style.SUCCESS(resumen))