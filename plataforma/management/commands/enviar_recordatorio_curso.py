# plataforma/management/commands/enviar_recordatorio_curso.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Q 
from datetime import timedelta 
import logging

from plataforma.models import Comision, DatosDeEstudiantes 

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envía un recordatorio 10 días antes de la fecha de inicio del curso.'

    def handle(self, *args, **options):
        
        # 1. Definir la fecha objetivo (Hoy + 10 días)
        hoy = timezone.now().date()
        fecha_objetivo = hoy + timedelta(days=10)
        
        self.stdout.write(self.style.SUCCESS(f"Iniciando envío de recordatorios para cursos que inician el: {fecha_objetivo}"))

        # 2. Buscar Comisiones cuya fecha de inicio sea EXACTAMENTE la fecha objetivo.
        try:
            comisiones_a_notificar = Comision.objects.filter(
                fecha_inicio=fecha_objetivo 
            ).select_related('id_curso')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al consultar Comisiones: {e}"))
            return

        if not comisiones_a_notificar.exists():
            self.stdout.write("No hay cursos programados para iniciar en 10 días.")
            return

        enviados = 0
        errores = 0

        for comision in comisiones_a_notificar:
            curso = comision.id_curso
            
            # 3. Obtener los alumnos inscritos
            alumnos = DatosDeEstudiantes.objects.filter(
                Q(cursando1=comision) | Q(cursando2=comision) | Q(cursando3=comision) |
                Q(cursando4=comision) | Q(cursando5=comision) | Q(cursando6=comision) |
                Q(cursando7=comision) | Q(cursando8=comision) | Q(cursando9=comision)
            ).distinct()

            self.stdout.write(f"Curso: {curso.nombre_curso} | Comisión {comision.numero_comision} | Alumnos a notificar: {alumnos.count()}")

            for alumno in alumnos:
                if not alumno.correo or '@' not in alumno.correo:
                    continue

                # 4. Preparar contexto
                context = {
                    'nombre': alumno.nombre,
                    'curso': curso.nombre_curso,
                    'fecha_inicio': comision.fecha_inicio.strftime('%d/%m/%Y'), 
                    'comision': comision.numero_comision,
                    'info_url': 'https://www.tecnomarema.com.ar/mis_cursos/' 
                }

                try:
                    # 🚨 CORRECCIÓN FINAL: Usamos la ruta consistente con tu otro script
                    html_message = render_to_string('registration/recordatorio_curso.html', context)
                    plain_message = strip_tags(html_message)

                    msg = EmailMultiAlternatives(
                        subject=f"⏳ ¡Cuenta Regresiva! Tu Curso {curso.nombre_curso} Inicia en 10 Días 🚀",
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