# plataforma/management/commands/enviar_notificacion_tutor_ausente.py

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
)


class Command(BaseCommand):
    help = 'Envía recordatorio firme y cálido a TUTORES que faltaron a clase'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=1, help='Días atrás (1 = ayer)')
        parser.add_argument('--dry-run', action='store_true', help='Solo prueba, no envía')

    def handle(self, *args, **options):
        dias_atras = options['dias']
        dry_run = options['dry_run']
        fecha_buscar = date.today() - timedelta(days=dias_atras)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Buscando TUTORES ausentes del {fecha_buscar.strftime('%d/%m/%Y')}..."
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

            # 2. Solo los que tienen rol 'tutor' en PerfilUsuario
            tutores_con_perfil = PerfilUsuario.objects.filter(
                rol='tutor',
                id_estudiante__in=inscriptos
            ).select_related('id_estudiante')

            tutores_ids = [p.id_estudiante_id for p in tutores_con_perfil]

            if not tutores_ids:
                continue

            # 3. Quiénes asistieron ese día (tienen registro)
            asistieron = AsistenciaClase.objects.filter(
                clase=clase,
                comision=comision,
                fecha_clase=fecha_buscar
            ).values_list('estudiante_id', flat=True)

            # 4. Tutores ausentes
            ausentes_ids = [pk for pk in tutores_ids if pk not in asistieron]

            for pk in ausentes_ids:
                tutor = DatosDeEstudiantes.objects.get(id_estudiante=pk)

                context = {
                    'nombre': tutor.nombre.split()[0],
                    'fecha_clase': fecha_buscar.strftime('%d/%m/%Y'),
                    'hora_clase': clase_com.horario.strftime('%H:%M'),
                    'numero_clase': clase.numero_clase,
                    'nombre_clase': clase.nombre_clase,
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    'link_calendario': f"http://127.0.0.1:8000/calendario/{comision.id_comision}/",
                }

                html_message = render_to_string(
                    'registration/notificacion_ausencia_tutor.html',
                    context
                )

                subject = f"Te necesitamos en clase, {tutor.nombre.split()[0]} – Tutoría {curso.nombre_curso}"

                if dry_run:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"[TUTOR - PRUEBA] → {tutor.correo} | {curso.nombre_curso} - Clase {clase.numero_clase}"
                        )
                    )
                else:
                    try:
                        send_mail(
                            subject=subject,
                            message="",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[tutor.correo.strip().lower()],
                            html_message=html_message,
                            fail_silently=False,
                        )
                        self.stdout.write(self.style.SUCCESS(f"Enviado a tutor → {tutor.correo}"))
                        enviados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error tutor → {tutor.correo}: {e}"))

        resumen = f"Listo! {enviados} recordatorios enviados a TUTORES"
        if dry_run:
            resumen += " (modo prueba)"
        self.stdout.write(self.style.SUCCESS(resumen))