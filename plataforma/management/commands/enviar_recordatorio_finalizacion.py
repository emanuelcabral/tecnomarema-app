# plataforma/management/commands/enviar_recordatorio_finalizacion.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db import models
from django.db.models import Max 
from datetime import timedelta 
import logging

from plataforma.models import ClaseComision, Comision, DatosDeEstudiantes 

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envía un recordatorio de la inminente finalización del curso (10 días antes de la última clase).'

    def handle(self, *args, **options):
        
        # 1. Definir la fecha objetivo de la última clase: Dentro de 10 días.
        hoy = timezone.now().date()
        fecha_objetivo_ultima_clase = hoy + timedelta(days=10) # El correo se envía hoy.
        
        self.stdout.write(self.style.SUCCESS(
            f"Buscando cursos cuya ÚLTIMA CLASE será el: {fecha_objetivo_ultima_clase} (Modo Pruebas)"
        ))

        # 2. Encontrar las comisiones cuya última clase ocurre en la fecha objetivo (dentro de 10 días).
        try:
            # Encontramos la fecha máxima de clase para cada comisión
            ultimas_clases = ClaseComision.objects.values('comision').annotate(
                ultima_fecha=Max('fecha')
            )

            # Filtramos las comisiones donde la última fecha es exactamente la fecha objetivo futura.
            comisiones_a_notificar_data = [
                item for item in ultimas_clases 
                if item['ultima_fecha'] == fecha_objetivo_ultima_clase
            ]
            
            comisiones_a_notificar_ids = [item['comision'] for item in comisiones_a_notificar_data]

            comisiones_a_notificar = Comision.objects.filter(
                id_comision__in=comisiones_a_notificar_ids
            ).select_related('id_curso') 

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al consultar Comisiones o Clases: {e}"))
            return

        if not comisiones_a_notificar.exists():
            self.stdout.write("No hay cursos con última clase programada para dentro de 10 días.")
            return

        enviados = 0
        errores = 0

        for comision in comisiones_a_notificar:
            curso = comision.id_curso
            
            # La fecha de la última clase es la fecha objetivo.
            fecha_ultima_clase = fecha_objetivo_ultima_clase 
            
            # 🚨 CÁLCULOS CLAVE:
            fecha_limite_entrega = fecha_ultima_clase + timedelta(days=10) # Última clase + 10 días
            fecha_fin_correcciones = fecha_ultima_clase + timedelta(days=30) # Última clase + 30 días
            
            alumnos = DatosDeEstudiantes.objects.filter(
                models.Q(cursando1=comision) | models.Q(cursando2=comision) | models.Q(cursando3=comision) |
                models.Q(cursando4=comision) | models.Q(cursando5=comision) | models.Q(cursando6=comision) |
                models.Q(cursando7=comision) | models.Q(cursando8=comision) | models.Q(cursando9=comision)
            ).distinct()

            self.stdout.write(
                f"Curso: {curso.nombre_curso} | Comisión {comision.numero_comision} | ÚLtima clase: {fecha_ultima_clase.strftime('%d/%m')} | Límite Entrega: {fecha_limite_entrega.strftime('%d/%m')}"
            )

            for alumno in alumnos:
                if not alumno.correo or '@' not in alumno.correo:
                    continue

                context = {
                    'nombre': alumno.nombre,
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    # Datos importantes para el alumno:
                    'fecha_ultima_clase': fecha_ultima_clase.strftime('%d/%m/%Y'),
                    'fecha_limite_entrega': fecha_limite_entrega.strftime('%d/%m/%Y'), 
                    'fecha_fin_correcciones': fecha_fin_correcciones.strftime('%d/%m/%Y'),
                    'link_entrega': 'https://www.tecnomarema.com.ar/home/' 
                }

                try:
                    html_message = render_to_string('registration/recordatorio_finalizacion.html', context) 
                    plain_message = strip_tags(html_message)

                    msg = EmailMultiAlternatives(
                        subject=f"🚨 ¡ATENCIÓN! Finaliza {curso.nombre_curso} en 10 Días",
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