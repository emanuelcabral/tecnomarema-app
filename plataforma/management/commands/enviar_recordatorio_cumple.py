# plataforma/management/commands/enviar_recordatorio_cumple.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging
# Importamos funciones de base de datos para extraer el día y el mes
from django.db.models.functions import ExtractDay, ExtractMonth

# Importamos el modelo DatosDeEstudiantes
from plataforma.models import DatosDeEstudiantes 

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envía un saludo de cumpleaños con una oferta especial (2x1) a los alumnos en la fecha de su cumpleaños.'

    def handle(self, *args, **options):
        
        # 1. Obtener el día y el mes actual
        hoy = timezone.now().date()
        dia_actual = hoy.day
        mes_actual = hoy.month
        
        self.stdout.write(self.style.SUCCESS(
            f"Buscando cumpleaños para la fecha de hoy: {dia_actual}/{mes_actual}"
        ))

        # 2. Filtrar alumnos cuyo día y mes de nacimiento coinciden con hoy.
        try:
            # Usamos funciones de DB para comparar solo el día y el mes de 'fecha_nacimiento'
            alumnos_cumple = DatosDeEstudiantes.objects.annotate(
                dia_nacimiento=ExtractDay('fecha_nacimiento'),
                mes_nacimiento=ExtractMonth('fecha_nacimiento')
            ).filter(
                dia_nacimiento=dia_actual,
                mes_nacimiento=mes_actual
            ).exclude(
                correo__isnull=True  # Aseguramos que tengan correo
            ).exclude(
                correo=''
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al consultar la tabla DatosDeEstudiantes: {e}"))
            self.stdout.write(self.style.WARNING("ADVERTENCIA: Asegúrate de que el campo de cumpleaños en tu modelo DatosDeEstudiantes se llama 'fecha_nacimiento' (DateField)."))
            return

        if not alumnos_cumple.exists():
            self.stdout.write("No hay alumnos celebrando su cumpleaños hoy.")
            return

        enviados = 0
        errores = 0

        self.stdout.write(
            f"Alumnos a notificar: {alumnos_cumple.count()}"
        )

        for alumno in alumnos_cumple:
            if not alumno.correo or '@' not in alumno.correo:
                errores += 1
                continue

            # 3. Preparar contexto para el template recordatorio_cumple.html
            context = {
                'nombre': alumno.nombre,
                # Link fijo al catálogo/promoción, como en tus otros scripts
                'link_catalogo': 'https://www.tecnomarema.com.ar/cursos/' 
            }

            try:
                # Usamos la ruta 'registration/' para consistencia
                html_message = render_to_string('registration/recordatorio_cumple.html', context) 
                plain_message = strip_tags(html_message)

                msg = EmailMultiAlternatives(
                    subject=f"🥳 ¡Feliz Cumpleaños {alumno.nombre}! 🎉 Te Regalamos un 2x1 en Tecno Marema",
                    body=plain_message,
                    from_email=None,
                    to=[alumno.correo]
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=False)
                
                enviados += 1
            except Exception as e:
                logger.error(f"Error enviando a {alumno.correo}: {repr(e)}")
                self.stdout.write(f"Error enviando a {alumno.correo}. Mensaje: {e}")
                errores += 1

        self.stdout.write(
            self.style.SUCCESS(f"FINALIZADO → Enviados: {enviados} | Errores: {errores}")
        )