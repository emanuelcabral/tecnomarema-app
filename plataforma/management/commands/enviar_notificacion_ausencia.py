# plataforma/management/commands/enviar_notificacion_ausencia.py

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db.models import Q

from plataforma.models import ReprogramacionDeClase, DatosDeEstudiantes 

class Command(BaseCommand):
    help = 'Envía notificaciones pendientes de reprogramación/cancelación'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("ENVIANDO NOTIFICACIONES PENDIENTES..."))

        # ENVÍA TODO LO PENDIENTE (sin importar la fecha)
        pendientes = ReprogramacionDeClase.objects.filter(
            notificado_correo=False
        ).select_related(
            'clase_afectada__comision__id_curso',
            'clase_afectada__clase',
            'clase_afectada__comision'
        )

        if not pendientes.exists():
            self.stdout.write("No hay notificaciones pendientes.")
            return

        enviados = 0
        errores = 0

        for log in pendientes:
            clase = log.clase_afectada
            comision = clase.comision
            curso = comision.id_curso

            estado = log.estado_final
            motivo = (log.motivo_principal or "") + (" - " + log.motivo_detalle if log.motivo_detalle else "")
            nueva_fecha = log.fecha_reprogramada.strftime('%d/%m/%Y') if log.fecha_reprogramada else "A confirmar"
            fecha_original = log.fecha_original.strftime('%d/%m/%Y') if log.fecha_original else clase.fecha.strftime('%d/%m/%Y')

            alumnos = DatosDeEstudiantes.objects.filter(
                Q(cursando1=comision) | Q(cursando2=comision) | Q(cursando3=comision) |
                Q(cursando4=comision) | Q(cursando5=comision) | Q(cursando6=comision) |
                Q(cursando7=comision) | Q(cursando8=comision) | Q(cursando9=comision)
            ).distinct()

            for alumno in alumnos:
                if not alumno.correo or '@' not in alumno.correo:
                    continue

                context = {
                    'nombre': alumno.nombre or "Alumno",
                    'curso': curso.nombre_curso,
                    'comision': getattr(comision, 'numero_comision', comision.id_comision) or comision.id_comision,
                    'nombre_clase': clase.clase.nombre_clase,
                    'fecha_original': fecha_original,
                    'hora_original': clase.horario.strftime('%H:%M'),
                    'estado': estado,
                    'motivo': motivo or "Motivo no especificado",
                    'nueva_fecha': nueva_fecha,
                    'link_plataforma': 'https://www.tecnomarema.com.ar/calendario/'
                }

                try:
                    html = render_to_string('registration/notificacion_ausencia.html', context)
                    text = strip_tags(html)
                    subject = f"CLASE {estado.upper()}: {curso.nombre_curso}"

                    msg = EmailMultiAlternatives(subject, text, None, [alumno.correo])
                    msg.attach_alternative(html, "text/html")
                    msg.send(fail_silently=False)
                    enviados += 1
                except Exception as e:
                    errores += 1

            log.notificado_correo = True
            log.save(update_fields=['notificado_correo'])

        self.stdout.write(self.style.SUCCESS(f"FINALIZADO → Enviados: {enviados} | Errores: {errores}"))