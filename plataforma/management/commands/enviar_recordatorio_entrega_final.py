# plataforma/management/commands/enviar_recordatorio_entrega_final.py

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from plataforma.models import (
    Comision,
    DatosDeEstudiantes,
    PerfilUsuario,
    RegistroPago,  # opcional: para verificar que pagó
)


class Command(BaseCommand):
    help = 'Envía recordatorio de entrega final 8 días después del fin de cada comisión'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo muestra, no envía')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy = timezone.now().date()
        fecha_objetivo = hoy - timedelta(days=8)  # comisiones que terminaron hace exactamente 8 días

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Buscando comisiones que finalizaron el {fecha_objetivo.strftime('%d/%m/%Y')} para enviar recordatorio..."
            )
        )

        comisiones_finalizadas = Comision.objects.filter(
            fecha_fin=fecha_objetivo,
            estado_comision='finalizado'
        ).select_related('id_curso')

        if not comisiones_finalizadas.exists():
            self.stdout.write(self.style.WARNING("No hay comisiones que hayan terminado hace 8 días."))
            return

        enviados = 0
        total_alumnos = 0

        for comision in comisiones_finalizadas:
            curso = comision.id_curso

            # Alumnos inscriptos en esta comisión (cursando1 a cursando5)
            inscriptos = DatosDeEstudiantes.objects.filter(
                cursando1=comision
            ) | DatosDeEstudiantes.objects.filter(cursando2=comision) | \
              DatosDeEstudiantes.objects.filter(cursando3=comision) | \
              DatosDeEstudiantes.objects.filter(cursando4=comision) | \
              DatosDeEstudiantes.objects.filter(cursando5=comision)

            # Solo alumnos reales (rol='alumno')
            alumnos = PerfilUsuario.objects.filter(
                rol='alumno',
                id_estudiante__in=inscriptos
            ).select_related('id_estudiante')

            total_alumnos += alumnos.count()

            for perfil in alumnos:
                alumno = perfil.id_estudiante

                # Opcional: verificar que haya pagado el curso (descomentar si querés)
                # if not RegistroPago.objects.filter(estudiante=alumno, comision=comision, estado_pago='Aprobado').exists():
                #     continue

                context = {
                    'nombre': alumno.nombre.split()[0],
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    'fecha_limite': (comision.fecha_fin + timedelta(days=15)).strftime('%d/%m/%Y'),
                    'link_entrega': f"https://127.0.0.1:8000/entrega-proyecto/{comision.id_comision}/",  # Cambiar por tu URL real
                }

                html_message = render_to_string(
                    'registration/recordatorio_entrega_final.html',
                    context
                )

                subject = f"¡Última chance para tu certificado, {alumno.nombre.split()[0]}! – {curso.nombre_curso}"

                if dry_run:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"[PRUEBA] → {alumno.correo} | {curso.nombre_curso} Comisión {comision.numero_comision}"
                        )
                    )
                else:
                    try:
                        send_mail(
                            subject=subject,
                            message="",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[alumno.correo.strip().lower()],
                            html_message=html_message,
                            fail_silently=False,
                        )
                        self.stdout.write(self.style.SUCCESS(f"Enviado → {alumno.correo}"))
                        enviados += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error → {alumno.correo}: {e}"))

        resumen = f"¡Listo! {enviados} recordatorios de entrega final enviados"
        if dry_run:
            resumen += f" (de {total_alumnos} alumnos - modo prueba)"
        self.stdout.write(self.style.SUCCESS(resumen))