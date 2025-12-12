# plataforma/management/commands/enviar_notificacion_alumno_ausente.py

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta

from plataforma.models import (
    AsistenciaClase,
    DatosDeEstudiantes,
    Comision,
    Clase,
    ClaseComision,
    PerfilUsuario,
)  # <-- paréntesis cerrado


class Command(BaseCommand):
    help = 'Envía correo motivador SOLO a alumnos reales que faltaron'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=1)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dias_atras = options['dias']
        dry_run = options['dry_run']
        fecha_buscar = date.today() - timedelta(days=dias_atras)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Buscando alumnos que faltaron el {fecha_buscar.strftime('%d/%m/%Y')}..."
            )
        )

        clases_del_dia = ClaseComision.objects.filter(
            fecha=fecha_buscar
        ).select_related('comision__id_curso', 'clase')

        if not clases_del_dia.exists():
            self.stdout.write(self.style.WARNING("No hubo clases ese día."))
            return

        enviados = 0

        for clase_com in clases_del_dia:
            comision = clase_com.comision
            clase = clase_com.clase
            curso = comision.id_curso

            # 1. Inscriptos en esta comisión
            inscriptos = DatosDeEstudiantes.objects.filter(
                cursando1=comision
            ) | DatosDeEstudiantes.objects.filter(cursando2=comision) | \
              DatosDeEstudiantes.objects.filter(cursando3=comision) | \
              DatosDeEstudiantes.objects.filter(cursando4=comision) | \
              DatosDeEstudiantes.objects.filter(cursando5=comision)

            # 2. Solo los que tienen PerfilUsuario con rol='alumno'
            alumnos_con_perfil = PerfilUsuario.objects.filter(
                rol='alumno',
                id_estudiante__in=inscriptos
            ).select_related('id_estudiante')

            alumnos_ids = [p.id_estudiante_id for p in alumnos_con_perfil]

            if not alumnos_ids:
                continue

            # 3. Quiénes asistieron ese día
            asistieron = AsistenciaClase.objects.filter(
                clase=clase,
                comision=comision,
                fecha_clase=fecha_buscar
            ).values_list('estudiante_id', flat=True)

            # 4. Ausentes
            ausentes_ids = [pk for pk in alumnos_ids if pk not in asistieron]

            for pk in ausentes_ids:
                estudiante = DatosDeEstudiantes.objects.get(id_estudiante=pk)

                context = {
                    'nombre': estudiante.nombre.split()[0],
                    'fecha_clase': fecha_buscar.strftime('%d/%m/%Y'),
                    'hora_clase': clase_com.horario.strftime('%H:%M'),
                    'numero_clase': clase.numero_clase,
                    'nombre_clase': clase.nombre_clase,
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    'link_calendario': f"http://127.0.0.1:8000/calendario/{comision.id_comision}/",
                }

                html_message = render_to_string(
                    'registration/notificacion_ausencia_alumno.html',
                    context
                )

                subject = f"Te extrañamos en clase, {estudiante.nombre.split()[0]}"

                if dry_run:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"[PRUEBA] {estudiante.correo} | {curso.nombre_curso} - Clase {clase.numero_clase}"
                        )
                    )
                else:
                    try:
                        send_mail(
                            subject=subject,
                            message="",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[estudiante.correo.strip().lower()],
                            html_message=html_message,
                            fail_silently=False,
                        )
                        self.stdout.write(self.style.SUCCESS(f"Enviado {estudiante.correo}"))
                        enviados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error {estudiante.correo}: {e}"))

        resumen = f"¡Listo! {enviados} correos enviados solo a ALUMNOS"
        if dry_run:
            resumen += " (modo prueba)"
        self.stdout.write(self.style.SUCCESS(resumen))