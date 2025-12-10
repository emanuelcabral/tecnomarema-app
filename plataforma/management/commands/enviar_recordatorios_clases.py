# plataforma/management/commands/enviar_recordatorios_clases.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from plataforma.models import ClaseComision, Comision, DatosDeEstudiantes
from django.db import models # Necesario para models.Q
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envía recordatorios de clase el mismo día a las 08:00 hs (usando tu plantilla actual)'

    def handle(self, *args, **options):
        hoy = timezone.now().date()
        ahora = timezone.now()
        hora_actual = ahora.time()

        # Bloque de control de horario COMENTADO para permitir PRUEBAS
        # if not (8 <= hora_actual.hour < 9 and hora_actual.minute < 10):
        #     self.stdout.write("No es horario de envío (08:00–08:10 hs). Saltando...")
        #     return

        self.stdout.write(self.style.SUCCESS(f"Iniciando envío de recordatorios para el {hoy} (Modo Pruebas)"))

        # Todas las clases que ocurren HOY
        try:
            clases_hoy = ClaseComision.objects.filter(
                fecha=hoy
            ).select_related(
                'clase',
                'clase__curso',
                'comision',
                'comision__id_curso'
            ) # 🚨 CORRECCIÓN: Se eliminó el prefetch_related problemático.
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al consultar ClasesComision: {e}"))
            return

        if not clases_hoy.exists():
            self.stdout.write("No hay clases programadas para hoy.")
            return

        enviados = 0
        errores = 0

        for clase_com in clases_hoy:
            clase = clase_com.clase
            comision = clase_com.comision
            curso = comision.id_curso

            # Link y horario reales de esta comisión
            link_clase = clase_com.link.strip() if clase_com.link else "Link pendiente (te lo pasamos pronto)"
            hora_inicio = clase_com.horario.strftime('%H:%M hs')

            # Todos los alumnos que tienen esta comisión en cualquiera de sus cursandoX
            # Esta consulta es correcta y reemplaza la necesidad del prefetch_related
            alumnos = DatosDeEstudiantes.objects.filter(
                models.Q(cursando1=comision) |
                models.Q(cursando2=comision) |
                models.Q(cursando3=comision) |
                models.Q(cursando4=comision) |
                models.Q(cursando5=comision) |
                models.Q(cursando6=comision) |
                models.Q(cursando7=comision) |
                models.Q(cursando8=comision) |
                models.Q(cursando9=comision)
            ).distinct()

            self.stdout.write(f"Clase: {clase.nombre_clase} | Comisión {comision.numero_comision} | Alumnos: {alumnos.count()}")

            for alumno in alumnos:
                if not alumno.correo or '@' not in alumno.correo:
                    continue

                context = {
                    'nombre': alumno.nombre,
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    'nombre_clase': clase.nombre_clase,
                    'hora_inicio': hora_inicio,
                    'link_clase': link_clase,
                }

                try:
                    # Usamos la ruta 'registration/recordatorio_clase.html' consistente con tu código
                    html_message = render_to_string('registration/recordatorio_clase.html', context)
                    plain_message = strip_tags(html_message)

                    send_mail(
                        subject=f"¡Hoy tenés clase de {curso.nombre_curso}! ⏰ {hora_inicio}",
                        message=plain_message,
                        from_email=None,
                        recipient_list=[alumno.correo],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    enviados += 1
                except Exception as e:
                    logger.error(f"Error enviando a {alumno.correo}: {e}")
                    self.stdout.write(f"Error enviando a {alumno.correo}: {e}")
                    errores += 1

        self.stdout.write(
            self.style.SUCCESS(f"FINALIZADO → Enviados: {enviados} | Errores: {errores}")
        )