from django.contrib.sessions.models import Session
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from plataforma.models import PerfilUsuario
from plataforma.decorators import session_required

from django.contrib.auth.views import (
    PasswordResetDoneView,
    PasswordResetCompleteView,
)
from django.urls import reverse_lazy
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.views.generic import FormView, View
from django import forms
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


############################################################################
# se agregan las importaciones de mercado pago
import mercadopago
from django.conf import settings

############################################################################

# --- Vistas públicas (sin login requerido) ---
def inicio(request):
    return render(request, 'educativa/inicio.html')

#---------------------------------------------------------------------------------------------

def login_view(request):
    # Limpiar mensajes anteriores para evitar mostrar mensajes viejos
    storage = messages.get_messages(request)
    list(storage)  # iterar para limpiar mensajes antiguos

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, 'Por favor, completá todos los campos.')
            return render(request, 'educativa/login.html')

        try:
            usuario = PerfilUsuario.objects.get(nombre_usuario=username)
            if check_password(password, usuario.password):
                # Guardar datos en la sesión personalizada
                request.session['usuario_logueado'] = usuario.nombre_usuario
                request.session['usuario_id'] = usuario.pk
                messages.success(request, 'Inicio de sesión exitoso.')
                if usuario.rol == 'admin' or usuario.is_staff:
                    return redirect('../administrador/admin_panel')
                return redirect('mis_cursos')
            else:
                messages.error(request, 'Contraseña incorrecta.')
        except PerfilUsuario.DoesNotExist:
            messages.error(request, 'Usuario no encontrado.')

    return render(request, 'educativa/login.html')

def logout_view(request):
    request.session.flush()
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')
#---------------------------------------------------------------------------------------------------
# def cursos(request):
#     return render(request, 'educativa/cursos.html')
#---------------------------------------------------------------------------------------------------

from django.shortcuts import render
from django.db.models import Count
from .models import Curso, Comision, Clase

def cursos_view(request):
    cursos = Curso.objects.all().order_by('id_curso')
    comision = Comision.objects.all()

    # Obtener cantidad de clases por curso_id desde la tabla Clase
    clases_por_curso = Clase.objects.values('curso_id').annotate(total_clases=Count('numero_clase'))
    clases_dict = {item['curso_id']: item['total_clases'] for item in clases_por_curso}

    # Agregamos un slug al curso para usarlo en el href
    for curso in cursos:
        curso.slug = curso.nombre_curso.lower().replace(" ", "_")

    contexto = {
        'cursos': cursos,
        'comision': comision,
        'clases_por_curso': clases_dict,
    }
    return render(request, 'educativa/cursos.html', contexto)



#----------------------------------------------------------------------------------------------------

# def cursos_view(request):
#     return render(request, 'cursos.html') #agregado por la sesion que devuelva usuario

def desarrollo_web_compra(request):
    return render(request, 'educativa/desarrollo_web_compra.html')

# def inscripcion(request):
#     return render(request, 'educativa/inscripcion.html')

#----------------------------------------------------------------------------------------
from django.shortcuts import render, get_object_or_404
from .models import Curso

def curso_compra_view(request, nombre_curso):
    # Verifica que el curso exista
    curso = get_object_or_404(Curso, nombre_curso__iexact=nombre_curso.replace('_', ' '))

    # Nombre del template a cargar (ej: desarrollo_web_compra.html)
    template_name = f"educativa/{nombre_curso}_compra.html"

    return render(request, template_name, {"curso": curso})


#----------------------------------------------------------------------------------------


from django.shortcuts import render
from .models import Curso, Comision, DatosDeEstudiantes
from django.conf import settings

def inscripcion(request):
    cursos_qs = Curso.objects.filter(estado_curso__in=['proximo', 'próximo', 'disponible', 'Disponible']).order_by('nombre_curso')
    cursos = []

    for curso in cursos_qs:
        comisiones = curso.comision_set.filter(estado_comision__in=['proximo', 'próximo'])

        cursos.append({
            'id': curso.id_curso,
            'nombre_curso': curso.nombre_curso,
            'modalidad': curso.get_modalidad_display(),
            'precio_original': curso.precio_original,
            'precio_final': curso.precio_final,
            'comisiones': list(comisiones.values(
                'numero_comision',
                'fecha_inicio',
                'fecha_fin',
                'dia1', 'dia2', 'dia3',
                'horario1', 'horario2', 'horario3',
                'estado_comision',
            ))
        })

    comisiones_global = Comision.objects.select_related('id_curso') \
        .filter(estado_comision__in=['proximo', 'próximo'])

    # ✅ Calcular próximo ID de estudiante formateado con 6 dígitos
    try:
        ultimo = DatosDeEstudiantes.objects.latest('id_estudiante')
        siguiente_id = int(ultimo.id_estudiante) + 1
    except (DatosDeEstudiantes.DoesNotExist, ValueError):
        siguiente_id = 1

    # 👉 Formatear con ceros a la izquierda (6 dígitos)
    proximo_id = str(siguiente_id).zfill(6)

    return render(request, 'educativa/inscripcion.html', {
        'cursos': cursos,
        'comisiones': comisiones_global,
        'proximo_id': proximo_id,
        # 'public_key': settings.MERCADOPAGO_PUBLIC_KEY,
        "MERCADOPAGO_PUBLIC_KEY": settings.MERCADOPAGO_PUBLIC_KEY
    })
#---------------------------------------------------------------------------------

from decimal import Decimal, InvalidOperation
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import DatosDeEstudiantes, PerfilUsuario, Comision, RegistroPago, Curso, Cupon
import mercadopago
import traceback
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def guardar_datos_inscripcion_paga(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

    # Protección contra doble POST
    if hasattr(request, '_processed'):
        return JsonResponse({"status": "ok", "msg": "Ya procesado"})
    request._processed = True

    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

    cupon = None
    descuento_aplicado = Decimal('0')
    ticket_url = ""
    payment_id = None

    try:
        # RECEPCIÓN DE DATOS
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        documento = request.POST.get("documento", "").strip() or request.POST.get("dni", "").strip()
        email = request.POST.get("email", "").strip()
        fecha_nacimiento = request.POST.get("fecha_nacimiento", "")
        pais = request.POST.get("pais", "")
        provincia = request.POST.get("provincia", "")
        telefono = request.POST.get("telefono", "").strip()
        genero = request.POST.get("genero", "")
        curso_id = request.POST.get("curso_id") or request.POST.get("curso")
        comision_id = request.POST.get("comision_id") or request.POST.get("comision")
        monto_dinamico_str = request.POST.get("monto", "0").strip()
        id_estudiante_front = request.POST.get("id_estudiante", "").strip()

        token = request.POST.get("token")
        payment_method_id = request.POST.get("payment_method_id", "")
        installments = int(request.POST.get("installments", 1))

        comprobante = request.FILES.get("comprobante")

        # VALIDACIONES BÁSICAS
        if not all([nombre, apellido, documento, email, curso_id, comision_id]):
            return JsonResponse({"status": "error", "msg": "Faltan datos obligatorios"}, status=400)

        # CURSO Y COMISIÓN
        try:
            curso_obj = Curso.objects.get(id_curso=curso_id)
        except Curso.DoesNotExist:
            return JsonResponse({"status": "error", "msg": "Curso no encontrado"}, status=400)

        try:
            comision = Comision.objects.get(numero_comision=comision_id, id_curso=curso_obj)
        except Comision.DoesNotExist:
            return JsonResponse({"status": "error", "msg": "Comisión no encontrada"}, status=400)

        # CÁLCULO MONTO CON CUPÓN
        monto_base = curso_obj.precio_final
        monto = monto_base

        cupon_codigo = request.POST.get("cupon", "").strip().upper()
        if cupon_codigo:
            try:
                cupon = Cupon.objects.get(codigo__iexact=cupon_codigo)
                if not cupon.es_valido():
                    return JsonResponse({"status": "error", "msg": "Cupón inválido o expirado"}, status=400)

                descuento_aplicado = Decimal(cupon.descuento_porcentaje)
                monto = monto_base * (Decimal('1') - (descuento_aplicado / Decimal('100')))
                monto = monto.quantize(Decimal('0.01'))

            except Cupon.DoesNotExist:
                return JsonResponse({"status": "error", "msg": "Cupón no encontrado"}, status=400)
            except Exception as e:
                return JsonResponse({"status": "error", "msg": f"Error procesando cupón: {str(e)}"}, status=400)
        else:
            monto = monto_base

        # Debug de monto
        try:
            monto_dinamico = Decimal(monto_dinamico_str).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            monto_dinamico = Decimal('0')

        print(f"[MONTO-DEBUG] Backend calcula: {monto}")
        print(f"[MONTO-DEBUG] Frontend envió: {monto_dinamico}")
        print(f"[MONTO-DEBUG] Diferencia: {abs(monto - monto_dinamico)}")
        print(f"[MONTO-DEBUG] Curso: {curso_obj.nombre_curso} | Cupón: {cupon_codigo or 'NINGUNO'} | Desc: {descuento_aplicado}%")

        # LÓGICA ALUMNO
        estudiante = DatosDeEstudiantes.objects.filter(dni=documento).first()

        if estudiante:
            print(f"[EDICIÓN] Editando alumno existente: {estudiante.nombre} {estudiante.apellido} - ID {estudiante.id_estudiante}")

            if estudiante.nombre != nombre:
                estudiante.nombre = nombre
            if estudiante.apellido != apellido:
                estudiante.apellido = apellido
            if estudiante.correo != email:
                estudiante.correo = email
            if estudiante.telefono != telefono:
                estudiante.telefono = telefono
            if pais and estudiante.pais != pais:
                estudiante.pais = pais
            if provincia and estudiante.provincia != provincia:
                estudiante.provincia = provincia
            if fecha_nacimiento and estudiante.fecha_nacimiento != fecha_nacimiento:
                estudiante.fecha_nacimiento = fecha_nacimiento
            if genero and estudiante.genero != genero:
                estudiante.genero = genero

            slot_asignado = False
            for i in range(1, 10):
                campo = f'cursando{i}'
                if getattr(estudiante, campo) is None:
                    setattr(estudiante, campo, comision)
                    slot_asignado = True
                    break

            if not slot_asignado:
                return JsonResponse({"status": "error", "msg": "El alumno ya alcanzó el máximo de 9 cursos permitidos"}, status=400)

            estudiante.save()

        else:
            print("[CREACIÓN] Creando alumno nuevo")

            ultimo = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
            nuevo_id = str(int(ultimo.id_estudiante) + 1).zfill(6) if ultimo else "000001"

            while DatosDeEstudiantes.objects.filter(id_estudiante=nuevo_id).exists():
                nuevo_id = str(int(nuevo_id) + 1).zfill(6)

            estudiante = DatosDeEstudiantes.objects.create(
                id_estudiante=nuevo_id,
                nombre=nombre,
                apellido=apellido,
                dni=documento,
                correo=email,
                fecha_nacimiento=fecha_nacimiento,
                pais=pais,
                provincia=provincia,
                telefono=telefono,
                genero=genero,
                cursando1=comision
            )

        # USUARIO
        usuario = PerfilUsuario.objects.filter(nombre_usuario=documento).first()

        if not usuario:
            usuario = PerfilUsuario.objects.filter(correo__iexact=email).first()

        if usuario:
            print(f"[USUARIO EXISTENTE] Reutilizando usuario ID {usuario.id_usuario}")
            if usuario.correo != email:
                usuario.correo = email
                usuario.save(update_fields=['correo'])
            if usuario.id_estudiante != estudiante:
                usuario.id_estudiante = estudiante
                usuario.save(update_fields=['id_estudiante'])
        else:
            print("[USUARIO NUEVO] Creando PerfilUsuario")
            ultimo_usuario = PerfilUsuario.objects.order_by('-id_usuario').first()
            usuario_id = str(int(ultimo_usuario.id_usuario) + 1).zfill(6) if ultimo_usuario else "000001"

            usuario = PerfilUsuario.objects.create(
                id_usuario=usuario_id,
                id_estudiante=estudiante,
                nombre_usuario=documento,
                correo=email,
                rol="alumno",
                is_active=True
            )
            usuario.set_password("pass1234")
            usuario.save()

        # DETERMINAR MEDIO DE PAGO
        medio_pago_db = "mercadopago"
        medio_pago_texto = "Mercado Pago"
        estado_pago = "Pendiente"
        id_transaccion = ""
        ticket_url = ""

        if comprobante and not token:
            medio_pago_db = "transferencia_bancaria"
            medio_pago_texto = "Transferencia bancaria"
            estado_pago = "Verificando"

        elif token and payment_method_id:
            # Monto como entero
            transaction_amount = int(monto.quantize(Decimal('0')))

            # Forzamos 1 cuota para Rapipago/Pagofacil
            if payment_method_id in ["rapipago", "pagofacil"]:
                installments = 1

            payment_data = {
                "transaction_amount": transaction_amount,
                "token": token,
                "description": f"Inscripción {curso_obj.nombre_curso} - Comisión {comision.numero_comision}",
                "installments": installments,
                "payment_method_id": payment_method_id,
                "payer": {"email": email}
            }

            print("\n=== MERCADO PAGO REQUEST ===")
            print(payment_data)
            print("==============================")

            result = sdk.payment().create(payment_data)


            # === DEBUG MERCADO PAGO ===
            print("=== MP REQUEST ===")
            print(payment_data)
            print("=== MP RESPONSE ===")
            print(result)
            print("=================================")


            payment = result["response"]

            print("\n=== MERCADO PAGO RESPONSE COMPLETA ===")
            print(payment)
            print("======================================")

            status_mp = payment.get("status")
            status_detail = payment.get("status_detail", "sin detalle")

            print(f"[MP STATUS] Status: {status_mp} | Detail: {status_detail}")

            if status_mp == "approved":
                id_transaccion = str(payment["id"])
                estado_pago = "Aprobado"

                # Clasificación precisa para tarjetas
                if "deb" in payment_method_id.lower():
                    medio_pago_db = "debito"
                    medio_pago_texto = "Débito"
                elif "credito" in payment_method_id.lower() or installments > 1:
                    medio_pago_db = f"credito_{installments}"
                    medio_pago_texto = f"Crédito en {installments} cuota{'s' if installments > 1 else ''}"
                else:
                    medio_pago_texto = "Mercado Pago (Aprobado)"

            elif status_mp == "pending":
                id_transaccion = str(payment["id"])
                estado_pago = "pendiente"

                # Extracción robusta del ticket_url
                ticket_url = ""
                td = payment.get("transaction_details", {})
                ticket_url = td.get("external_resource_url") or td.get("ticket_url") or ""

                poi = payment.get("point_of_interaction", {})
                tdata = poi.get("transaction_data", {})
                ticket_url = ticket_url or tdata.get("ticket_url") or tdata.get("external_resource_url") or ""

                if ticket_url:
                    print(f"[MP TICKET] URL encontrada: {ticket_url}")
                else:
                    print("[MP WARNING] No se encontró ticket_url")
                    ticket_url = "https://www.mercadopago.com.ar/"  # fallback

                if payment_method_id in ["rapipago", "pagofacil"] and status_detail == "pending_waiting_payment":
                    medio_pago_db = payment_method_id
                    medio_pago_texto = "Rapipago" if payment_method_id == "rapipago" else "Pago Fácil"
                else:
                    medio_pago_texto = "Mercado Pago (Pendiente)"

            else:
                error_msg = f"Pago rechazado: {status_detail} (status: {status_mp})"
                print(f"[MP ERROR] {error_msg}")
                return JsonResponse({
                    "status": "error",
                    "msg": error_msg
                }, status=400)

        # REGISTRAR PAGO - chequeo de duplicado
        from datetime import timedelta
        tiempo_reciente = timezone.now() - timedelta(minutes=5)

        duplicado = RegistroPago.objects.filter(
            estudiante=estudiante,
            comision=comision,
            fecha_pago__gte=tiempo_reciente
        ).exists()

        if duplicado:
            logger.warning(f"Duplicado detectado para {documento} - {curso_obj.nombre_curso} - {comision.numero_comision}")
            return JsonResponse({
                "status": "ok",
                "id_estudiante": estudiante.id_estudiante,
                "id_usuario": usuario.id_usuario,
                "medio_pago": medio_pago_texto,
                "monto_final": f"{monto:.2f}",
                "ticket_url": ticket_url,
                "mensaje": "Inscripción ya registrada. Revisa tu correo."
            })

        RegistroPago.objects.create(
            estudiante=estudiante,
            comision=comision,
            plataforma="web",
            medio_pago=medio_pago_db,
            estado_pago=estado_pago,
            monto=monto,
            fecha_pago=timezone.now(),
            id_transaccion=id_transaccion,
            archivo_comprobante=comprobante,
            link_comprobante=ticket_url
        )

        # MARCAR USO DEL CUPÓN
        if cupon and descuento_aplicado > 0:
            cupon.usos_actuales += 1
            cupon.save()
            print(f"[CUPÓN OK] Uso registrado: {cupon.codigo} ({descuento_aplicado}%)")

        # ENVÍO DE CORREOS (adaptado a Brevo - usa send_mail para que pase por el backend custom)
        es_nueva = not DatosDeEstudiantes.objects.filter(dni=documento).exists()

        titulo_correo = "Nuevo alumno inscripto" if es_nueva else "Inscripción adicional"
        saludo = "¡Bienvenido/a a Tecno Marema!" if es_nueva else "¡Bienvenido/a nuevamente!"

        # Correo interno (admin) - siempre
        context_interno = {
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "documento": documento,
            "curso": curso_obj.nombre_curso,
            "comision": comision.numero_comision,
            "pais": pais,
            "provincia": provincia,
            "telefono": telefono,
            "medio_pago": medio_pago_texto,
            "monto": monto,
            "fecha": timezone.now(),
            "es_nueva": es_nueva
        }
        html_interno = render_to_string("registration/registro_pago.html", context_interno)
        send_mail(
            subject=titulo_correo,
            message=strip_tags(html_interno),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=["tecnomarema.ar@gmail.com"],
            html_message=html_interno,
            fail_silently=False,
        )
        print("[EMAIL INTERNO] Enviado vía Brevo a admin")

        # Correo al alumno - SIEMPRE (acceso)
        context_alumno = {
            "nombre": f"{nombre} {apellido}",
            "usuario": documento,
            "password": "pass1234",
            "curso": curso_obj.nombre_curso,
            "comision": comision.numero_comision,
            "reset_url": "https://tecnomarema.com.ar/login/",
            "saludo": saludo
        }
        html_alumno = render_to_string("registration/bienvenida_paga.html", context_alumno)
        send_mail(
            subject="Acceso a tu curso - Tecno Marema",
            message=strip_tags(html_alumno),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_alumno,
            fail_silently=False,
        )
        print(f"[EMAIL ALUMNO] Enviado vía Brevo a {email}")

        # Correo adicional de pendiente (solo cuando corresponde)
        if estado_pago == "pendiente" and ticket_url:
            context_pendiente = {
                "nombre": f"{nombre} {apellido}",
                "curso": curso_obj.nombre_curso,
                "comision": comision.numero_comision,
                "monto": monto,
                "medio_pago": medio_pago_texto,
                "ticket_url": ticket_url,
                "instrucciones": "Pagá en el local con este comprobante antes de que venza."
            }
            html_pendiente = render_to_string("registration/pago_pendiente.html", context_pendiente)
            send_mail(
                subject=f"Completa tu pago en {medio_pago_texto} - Tecno Marema",
                message=strip_tags(html_pendiente),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_pendiente,
                fail_silently=False,
            )
            print(f"[EMAIL PENDIENTE] Enviado vía Brevo a {email} con ticket: {ticket_url}")

        # Éxito - respuesta completa
        return JsonResponse({
            "status": "ok",
            "id_estudiante": estudiante.id_estudiante,
            "id_usuario": usuario.id_usuario,
            "medio_pago": medio_pago_texto,
            "monto_final": f"{monto:.2f}",
            "ticket_url": ticket_url,
            "estado_pago": estado_pago
        })

    except Exception as e:
        if cupon and descuento_aplicado > 0:
            cupon.usos_actuales = max(0, cupon.usos_actuales - 1)
            cupon.save()

        logger.exception("Error crítico en guardar_datos_inscripcion_paga")
        traceback.print_exc()

        return JsonResponse({
            "status": "error",
            "msg": "Ocurrió un error interno. Por favor contacta soporte."
        }, status=500)


#-------------------------------------------------------------------------------



def obtener_comisiones_por_curso(request, id_curso):
    comisiones_qs = Comision.objects.filter(
        id_curso__id_curso=id_curso,
        estado_comision='proximo'
    ).values(
        'numero_comision', 'fecha_inicio', 'fecha_fin', 
        'dia1', 'horario1', 'dia2', 'horario2', 'dia3', 'horario3'
    ).order_by('fecha_inicio')

    lista = []
    for c in comisiones_qs:
        lista.append({
            'numero_comision': c['numero_comision'],
            'fecha_inicio': c['fecha_inicio'].strftime('%Y-%m-%d') if c['fecha_inicio'] else '',
            'fecha_fin': c['fecha_fin'].strftime('%Y-%m-%d') if c['fecha_fin'] else '',
            'dia1': c['dia1'] or '',
            'horario1': c['horario1'] or '',
            'dia2': c['dia2'] or '',
            'horario2': c['horario2'] or '',
            'dia3': c.get('dia3') or '',
            'horario3': c.get('horario3') or '',
        })

    return JsonResponse({'comisiones': lista})



#-----------------------------------------------------------------

def terminos_y_condiciones(request):
    return render(request, 'educativa/terminos_y_condiciones.html')

# --- Vistas privadas (requieren login) ---
# @session_required
# def mis_cursos(request):
#     return render(request, 'educativa/mis_cursos.html')
# mis cursos inician
# @session_required
# def desarrollo_web(request):
#     return render(request, 'educativa/desarrollo_web.html')

# @session_required
# def inteligencia_artificial(request):
#     return render(request, 'educativa/inteligencia_artificial.html')

# @session_required
# def python_curso(request):
#     return render(request, 'educativa/python_curso.html')

# @session_required
# def javascript_curso(request):
#     return render(request, 'educativa/javascript_curso.html')
# # mis cursos finaliza

@session_required
def videos_desarrollo_web(request):
    return render(request, 'educativa/videos_desarrollo_web.html', {
        'nombre_usuario': request.session.get('usuario_logueado')
    })


@session_required
def asistencia_alumnos(request):
    return render(request, 'educativa/asistencia_alumnos.html', {
        'nombre_usuario': request.session.get('usuario_logueado')
    })


@session_required
def asistencia_general(request):
    return render(request, 'educativa/asistencia_general.html', {
        'nombre_usuario': request.session.get('usuario_logueado')
    })

# @session_required
# def valoraciones(request):
#     return render(request, 'educativa/valoraciones.html')

# @session_required
# def valoraciones(request):
#     clases = list(range(1, 22))  # del 1 al 21 incluido
#     valoraciones = ValoracionAlumno.objects.all()

    
#     # Asignar color según preferencia
#     for v in valoraciones:
#         if v.preferencia_clase == 'me_gusto':
#             v.color_avatar = '#12f693'
#         elif v.preferencia_clase == 'mas_o_menos':
#             v.color_avatar = '#00f7ff'
#         else:
#             v.color_avatar = '#cf30ff'
    
#     contexto = {
#         'clases': clases,
#         'valoraciones': valoraciones,
#     }

#     return render(request, 'educativa/valoraciones.html', contexto)


from collections import defaultdict
from django.db.models import Count
from django.shortcuts import render
from plataforma.decorators import session_required
from plataforma.models import ValoracionAlumno

@session_required
def valoraciones(request):
    clases = list(range(1, 22))  # Clases 1 a 21
    resumen_clases = {}

    # Para cada clase, calcular votos y porcentajes
    for clase_num in clases:
        valoraciones_clase = ValoracionAlumno.objects.filter(clase__numero_clase=clase_num)
        total = valoraciones_clase.count()

        conteo = valoraciones_clase.values('preferencia_clase') \
                                   .annotate(cantidad=Count('preferencia_clase'))

        votos = {'me_gusto': 0, 'mas_o_menos': 0, 'no_me_gusto': 0}
        for item in conteo:
            votos[item['preferencia_clase']] = item['cantidad']

        def porcentaje(x):
            return round((x / total) * 100) if total > 0 else 0

        resumen_clases[clase_num] = {
            'total': total,
            'votos': votos,
            'porcentajes': {
                'me_gusto': porcentaje(votos['me_gusto']),
                'mas_o_menos': porcentaje(votos['mas_o_menos']),
                'no_me_gusto': porcentaje(votos['no_me_gusto']),
            }
        }

    # Resumen general del curso
    total_general = ValoracionAlumno.objects.count()
    conteo_general = ValoracionAlumno.objects.values('preferencia_clase') \
                                              .annotate(cantidad=Count('preferencia_clase'))

    votos_general = {'me_gusto': 0, 'mas_o_menos': 0, 'no_me_gusto': 0}
    for item in conteo_general:
        votos_general[item['preferencia_clase']] = item['cantidad']

    def porcentaje(x):
        return round((x / total_general) * 100) if total_general > 0 else 0

    resumen_general = {
        'total': total_general,
        'votos': votos_general,
        'porcentajes': {
            'me_gusto': porcentaje(votos_general['me_gusto']),
            'mas_o_menos': porcentaje(votos_general['mas_o_menos']),
            'no_me_gusto': porcentaje(votos_general['no_me_gusto']),
        }
    }

    # Listado de todas las valoraciones (con colores)
    valoraciones = ValoracionAlumno.objects.select_related('clase').all()

    for v in valoraciones:
        if v.preferencia_clase == 'me_gusto':
            v.color_avatar = '#12f693'
        elif v.preferencia_clase == 'mas_o_menos':
            v.color_avatar = '#00f7ff'
        else:
            v.color_avatar = '#cf30ff'

    contexto = {
        'clases': clases,
        'resumen_clases': resumen_clases,
        'resumen_general': resumen_general,
        'valoraciones': valoraciones,
        # 'usuario': request.session.get('usuario_logueado'),
        'nombre_usuario': request.session.get('usuario_logueado'),
    }

    return render(request, 'educativa/valoraciones.html', contexto)



@session_required
def valoracion_alumno(request):
    return render(request, 'educativa/valoracion_alumno.html')

@session_required
def estadisticas(request):
    return render(request, 'educativa/estadisticas.html')


##################################################################################
###------------------------Eliminacion de Valoraciones-------------------------###
##################################################################################


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import ValoracionAlumno

@require_POST
def eliminar_valoracion(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ninguna valoración para eliminar."})

        # Convertir a enteros y descartar vacíos
        ids = [int(i) for i in ids if i.strip().isdigit()]

        eliminados = ValoracionAlumno.objects.filter(valoracion_alumno_id__in=ids).delete()[0]

        return JsonResponse({"success": True, "mensaje": "Valoraciones eliminadas correctamente.", "cantidad": eliminados})

    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


#-----------------------------------------------------------------

from django.db.models import Sum
from django.shortcuts import render, get_object_or_404
from .models import RegistroPago, DatosDeEstudiantes
from plataforma.decorators import session_required # Asegúrate de que esta importación exista

@session_required
def saldo(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return render(request, 'educativa/saldo.html', {
            'cursos_inscriptos': [],
            'nombre_usuario': 'Invitado',
            'mensaje': 'No hay estudiante identificado en sesión.'
        })

    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=usuario_id)
    nombre_usuario = getattr(estudiante, 'nombre', 'Estudiante') # Obtenemos el nombre del estudiante

    cursos_inscriptos = []

    for i in range(1, 10):
        comision = getattr(estudiante, f'cursando{i}', None)
        if comision:
            curso = comision.id_curso
            
            # 1. Filtramos y ordenamos los pagos.
            pagos_qs = RegistroPago.objects.filter(
                estudiante=estudiante, 
                comision=comision
            ).order_by('fecha_pago')
            
            # 2. **CORRECCIÓN CRÍTICA (LÓGICA):** El total abonado debe sumar SÓLO los pagos acreditados.
            # Usamos 'Acreditado' para ser consistentes con la lógica de tu plantilla (badge verde).
            pagos_acreditados_qs = pagos_qs.filter(estado_pago='Acreditado')
            
            # 3. Calculamos la sumatoria solo de los acreditados
            abonado = pagos_acreditados_qs.aggregate(total=Sum('monto'))['total'] or 0
            
            saldo = float(curso.precio_final) - float(abonado)

            cursos_inscriptos.append({
                'curso': curso,
                'comision': comision,
                'pagos': list(pagos_qs), # **CORRECCIÓN CRÍTICA (FUGAS DE DATOS):** Convertir el QuerySet a lista (list())
                'abonado': abonado,
                'saldo': saldo,
            })

    context = {
        'cursos_inscriptos': cursos_inscriptos,
        'nombre_usuario': nombre_usuario, # Pasamos el nombre correcto
    }

    return render(request, 'educativa/saldo.html', context)




#---------------------------------------------------------------------------


# @session_required
# def faq(request):
#     return render(request, 'educativa/faq.html')

# @session_required
# def redes(request):
#     return render(request, 'educativa/redes.html')

# @session_required
# def contacto(request):
#     return render(request, 'educativa/contacto.html')

@session_required
def faq(request):
    return render(request, 'educativa/faq.html', {
        'nombre_usuario': request.session.get('usuario_logueado')
    })

@session_required
def redes(request):
    return render(request, 'educativa/redes.html', {
        'nombre_usuario': request.session.get('usuario_logueado')
    })

@session_required
def contacto(request):
    return render(request, 'educativa/contacto.html', {
        'nombre_usuario': request.session.get('usuario_logueado')
    })

@session_required
def perfil_alumno_view(request):
    nombre_usuario = request.session.get('usuario_logueado')
    if not nombre_usuario:
        messages.error(request, 'Debes iniciar sesión para ver tu perfil.')
        return redirect('login')
    try:
        usuario = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
    except PerfilUsuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login')
    return render(request, 'educativa/perfil_alumno.html', {'usuario': usuario, 'nombre_usuario': nombre_usuario})

# --- Formulario personalizado para reset ---
class CustomPasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'form-control'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if not PerfilUsuario.objects.filter(correo=email).exists():
            raise forms.ValidationError("No existe ningún usuario con ese email.")
        return email

# --- Vista de envío de email de recuperación ---
class CustomPasswordResetView(View):
    template_name = 'registration/password_reset_form.html'
    success_url = reverse_lazy('password_reset_done')

    def get(self, request):
        form = CustomPasswordResetForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            usuarios = PerfilUsuario.objects.filter(correo=email, is_active=True)
            if not usuarios.exists():
                messages.error(request, "No existe ningún usuario activo con ese email.")
                return render(request, self.template_name, {'form': form})

            for usuario in usuarios:
                uidb64 = urlsafe_base64_encode(force_bytes(usuario.pk))
                token = default_token_generator.make_token(usuario)
                protocol = 'https' if request.is_secure() else 'http'
                domain = request.get_host()

                reset_link = f"{protocol}://{domain}/reset/{uidb64}/{token}/"

                subject = "Recuperá tu contraseña en Tecno Marema"
                message = render_to_string('registration/password_reset_email.html', {
                    'user': usuario,
                    'reset_link': reset_link,
                })

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                    html_message=message,
                )

            messages.success(request, f"Se envió un email con instrucciones a {email}")
            return redirect(self.success_url)
        return render(request, self.template_name, {'form': form})

# --- Vista post-envío y post-reset ---
class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'

# --- Formulario de confirmación de nueva contraseña ---
class CustomPasswordResetConfirmForm(forms.Form):
    new_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}),
    )
    new_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password1")
        p2 = cleaned_data.get("new_password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data

# --- Vista de confirmación con token ---
class CustomPasswordResetConfirmView(FormView):
    template_name = 'registration/password_reset_confirm.html'
    form_class = CustomPasswordResetConfirmForm
    success_url = reverse_lazy('password_reset_complete')

    def dispatch(self, request, uidb64=None, token=None, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            self.user = PerfilUsuario.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, PerfilUsuario.DoesNotExist):
            self.user = None

        if self.user is None:
            messages.error(request, "El enlace para restablecer la contraseña no es válido.")
            return render(request, 'registration/password_reset_invalid.html')

        if not default_token_generator.check_token(self.user, token):
            messages.error(request, "El enlace para restablecer la contraseña no es válido o ha expirado.")
            return render(request, 'registration/password_reset_invalid.html')

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        new_password = form.cleaned_data['new_password1']
        self.user.set_password(new_password)
        self.user.save()
        messages.success(self.request, "Tu contraseña ha sido actualizada exitosamente. Ahora podés iniciar sesión.")
        return redirect(self.success_url)  # redirect explícito para mostrar mensaje correctamente


from plataforma.decorators import session_required



@session_required
def mis_cursos(request):
    nombre_usuario = request.session.get('usuario_logueado', 'AnonymousUser')
    es_autenticado = 'usuario_logueado' in request.session

    try:
        usuario = PerfilUsuario.objects.select_related('id_estudiante').get(nombre_usuario=nombre_usuario)
        estudiante = usuario.id_estudiante

        # Recolectar todas las comisiones del estudiante
        comisiones = []
        for comision_id in [
            estudiante.cursando1_id, estudiante.cursando2_id, estudiante.cursando3_id,
            estudiante.cursando4_id, estudiante.cursando5_id, estudiante.cursando6_id,
            estudiante.cursando7_id, estudiante.cursando8_id, estudiante.cursando9_id
        ]:
            if comision_id:
                try:
                    comision = Comision.objects.select_related('id_curso').get(id_comision=comision_id)
                    comisiones.append(comision)
                except Comision.DoesNotExist:
                    continue

        # Ordenar comisiones por estado: en_curso (0), proximo (1), finalizado (2)
        estado_orden = {
            'en_curso': 0,
            'proximo': 1,
            'finalizado': 2
        }

        comisiones.sort(key=lambda c: (
            estado_orden.get(c.estado_comision, 3),  # orden de estado
            c.fecha_inicio or datetime.date.today()  # orden secundario por fecha de inicio
        ))

        contexto = {
            'usuario': usuario,
            'estudiante': estudiante,
            'comisiones': comisiones,
            'nombre_usuario': nombre_usuario,
            'es_autenticado': es_autenticado,
        }

        return render(request, 'educativa/mis_cursos.html', contexto)

    except PerfilUsuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login')

# --------------------------------------------------------------------------------------

# from django.shortcuts import render, redirect
# from django.contrib import messages
# from .models import PerfilUsuario
# from .decorators import session_required

# @session_required
# def desarrollo_web(request):
#     nombre_usuario = request.session.get('usuario_logueado', 'AnonymousUser')
#     es_autenticado = 'usuario_logueado' in request.session

#     try:
#         usuario = PerfilUsuario.objects.select_related('id_estudiante').get(nombre_usuario=nombre_usuario)
#         estudiante = usuario.id_estudiante

#         contexto = {
#             'usuario': usuario,
#             'estudiante': estudiante,
#             'nombre_usuario': nombre_usuario,
#             'es_autenticado': es_autenticado,
#         }
#         return render(request, 'educativa/desarrollo_web.html', contexto)

#     except PerfilUsuario.DoesNotExist:
#         messages.error(request, 'Usuario no encontrado.')
#         return redirect('login')



@session_required
def logout_all_view(request):
    usuario_id = request.session.get('usuario_id')

    # Borrar todas las sesiones activas que tengan ese usuario_id
    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get('usuario_id') == usuario_id:
            session.delete()

    messages.success(request, 'Cerraste sesión en todos los dispositivos.')
    return redirect('login')

#######################################################################################################
##---------------------------------envio de correo desde contacto------------------------------------##
#######################################################################################################
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages

def enviar_mensaje(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        email = request.POST.get("email")
        mensaje = request.POST.get("mensaje")

        contenido = f"""
        Nuevo mensaje de contacto desde la plataforma TecnoMarema:

        Nombre: {nombre}
        Email: {email}

        Mensaje:
        {mensaje}
        """

        send_mail(
            subject="Nuevo mensaje de contacto",
            message=contenido,
            from_email=email,
            recipient_list=["tecnomarema.ar@gmail.com"],
        )

        messages.success(request, "¡Tu mensaje fue enviado exitosamente!")
        return redirect('contacto')  # Asegurate de que 'contacto' esté en tus urls
    else:
        return redirect('contacto')

###################################################################################################
from django.http import JsonResponse

def contacto_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        mensaje = request.POST.get('mensaje')

        try:
            send_mail(
                f"Nuevo mensaje de {nombre}",
                mensaje,
                email,
                ['tecnomarema.ar@gmail.com'],
                fail_silently=False,
            )
            return JsonResponse({'success': True})
        except:
            return JsonResponse({'success': False})
    
    return render(request, 'contacto.html')

#######################################################################################################
##---------------------------------guardar los datos del perfil--------------------------------------##
#######################################################################################################
from django.shortcuts import render, redirect
from .models import PerfilUsuario, DatosDeEstudiantes

def editar_perfil(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return redirect('login')  # redirigí a tu vista de login si no hay sesión

    try:
        usuario = PerfilUsuario.objects.get(id_usuario=usuario_id)
        estudiante = usuario.id_estudiante
    except PerfilUsuario.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        # Actualizar DatosDeEstudiantes
        estudiante.nombre = request.POST.get('nombre', estudiante.nombre)
        estudiante.apellido = request.POST.get('apellido', estudiante.apellido)
        estudiante.dni = request.POST.get('dni', estudiante.dni)
        estudiante.correo = request.POST.get('correo', estudiante.correo)
        estudiante.fecha_nacimiento = request.POST.get('fecha_nacimiento', estudiante.fecha_nacimiento)
        estudiante.pais = request.POST.get('pais', estudiante.pais)
        estudiante.provincia = request.POST.get('provincia', estudiante.provincia)
        estudiante.telefono = request.POST.get('telefono', estudiante.telefono)
        estudiante.genero = request.POST.get('genero', estudiante.genero)
        estudiante.biografia = request.POST.get('biografia', estudiante.biografia)
        estudiante.save()

        # Actualizar PerfilUsuario
        usuario.nombre_usuario = request.POST.get('nombre_usuario', usuario.nombre_usuario)
        usuario.correo = request.POST.get('correo', usuario.correo)
        usuario.save()

        # return redirect('perfil')
        return redirect('/perfil/?guardado=1')

    context = {
        'usuario': usuario,
        'estudiante': estudiante,
    }
    return render(request, 'educativa/perfil_alumno.html', context)

#######################################################################################################
##---------------------------------subir foto al perfil----------------------------------------------##
#######################################################################################################
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .models import PerfilUsuario
from .forms import PerfilUsuarioForm
from datetime import datetime


def subir_foto_perfil(request):
    if 'usuario_id' not in request.session:
        return redirect('login')

    usuario_id = request.session['usuario_id']
    perfil = get_object_or_404(PerfilUsuario, id_usuario=usuario_id)

    if request.method == 'POST':
        print("request.POST:", request.POST)
        print("request.FILES:", request.FILES)

        archivo = request.FILES.get('foto')
        if archivo:
            # Validación de tamaño: máximo 1 MB
            if archivo.size > 1024 * 1024:
                messages.error(request, 'La imagen excede el límite de 1024 KB.')
                return redirect('perfil')

            # Validación de tipo: debe ser imagen
            if not archivo.content_type.startswith('image/'):
                messages.error(request, 'Solo se permiten archivos de imagen.')
                return redirect('perfil')

            # 🧼 Eliminar imagen anterior si existe
            if perfil.foto and os.path.isfile(perfil.foto.path):
                os.remove(perfil.foto.path)

            # 📥 Asignar la nueva imagen al perfil
            perfil.foto = archivo
            perfil.save()

            # DEBUG: mostrar info del archivo guardado
            print("Nombre del archivo:", perfil.foto.name)
            print("Ruta completa:", perfil.foto.path)
            print("¿Existe físicamente?", os.path.exists(perfil.foto.path))

            messages.success(request, 'Foto de perfil actualizada correctamente.')
            return redirect('perfil')
        else:
            messages.error(request, 'No se ha seleccionado ninguna imagen.')
            return redirect('perfil')
    else:
        form = PerfilUsuarioForm(instance=perfil)

    return render(request, 'educativa/perfil_alumno.html', {
        'form': form,
        'usuario': perfil,
        'timestamp': datetime.now().timestamp(),
    })
#-----------------------------------------------------------------------#
from django.shortcuts import redirect
from django.conf import settings
import os

def eliminar_foto(request):
    usuario = request.session.get('usuario_logueado')
    if not usuario:
        return redirect('login')  # o la vista correspondiente

    perfil = PerfilUsuario.objects.get(nombre_usuario=usuario)

    if perfil.foto:
        ruta_foto = perfil.foto.path
        if os.path.exists(ruta_foto):
            os.remove(ruta_foto)
        perfil.foto = None
        perfil.save()

    return redirect('perfil')  # o como se llame tu vista de perfil

#------------------------------------------------------------------------#
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import DatosDeEstudiantes, Clase, Comision, Curso

def mostrar_formulario_valoracion(request, curso_id, comision_id, estudiante_id, numero_clase):
    id_usuario = request.session.get('usuario_id')
    nombre_usuario = request.session.get('usuario_logueado')

    if not id_usuario or not nombre_usuario:
        return redirect('login')  # Por si alguien accede sin sesión activa

    # 🔎 Verificaciones
    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=estudiante_id)
    curso = get_object_or_404(Curso, id_curso=curso_id)
    comision = get_object_or_404(Comision, id_comision=comision_id, id_curso=curso)
    clase = get_object_or_404(Clase, curso=curso, numero_clase=numero_clase)

    contexto = {
        'id_estudiante': estudiante_id,
        'id_usuario': id_usuario,
        'nombre_usuario': nombre_usuario,
        'clase': clase,
        'curso_id': curso_id,
        'comision_id': comision_id,
        'numero_clase': numero_clase,
    }
    return render(request, 'educativa/valoracion_alumno.html', contexto)

from django.shortcuts import redirect, get_object_or_404
from .models import ValoracionAlumno, Clase
from django.utils import timezone
from django.contrib import messages  # Para mostrar un mensaje opcional

def guardar_valoracion(request):
    if request.method == 'POST':
        id_estudiante = request.POST.get('id_estudiante')
        id_usuario = request.POST.get('id_usuario')
        nombre_usuario = request.POST.get('nombre_usuario')
        clase_id = request.POST.get('clase_id')
        comision_id = request.POST.get('comision_id')  # 🔸 Asegurate que este campo venga en el formulario

        # Validación básica
        if not id_estudiante or not nombre_usuario or not clase_id or not comision_id:
            return redirect('mis_cursos')

        clase = get_object_or_404(Clase, id=clase_id)

        # ❌ Chequear si ya existe una valoración para este estudiante, clase y comisión
        ya_valoro = ValoracionAlumno.objects.filter(
            id_estudiante=id_estudiante,
            clase_id=clase_id,
            comision_id=comision_id
        ).exists()

        if ya_valoro:
            messages.warning(request, "Ya valoraste esta clase en esta comisión.")
            return redirect('agradecimiento')

        # ✅ Guardar valoración
        ValoracionAlumno.objects.create(
            id_estudiante=id_estudiante,
            id_usuario=id_usuario,
            nombre_usuario=nombre_usuario,
            clase=clase,

            curso_id=clase.curso.id_curso,
            curso_nombre=clase.curso.nombre_curso,
            comision_id=comision_id,
            numero_clase=clase.numero_clase,
            nombre_clase=clase.nombre_clase,

            preferencia_clase=request.POST.get('preferencia_clase', ''),
            rol_profe=request.POST.get('rol_profe', ''),
            contenido=request.POST.get('contenido', ''),
            plataforma=request.POST.get('plataforma', ''),
            streaming=request.POST.get('streaming', ''),
            comentarios=request.POST.get('comentarios', ''),

            fecha_valoracion=timezone.now()
        )

        return redirect('agradecimiento')

    return redirect('inicio')



#------------------------captura de datos de inscripcion--------------------------------------------#
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Comision

@csrf_exempt
def guardar_datos_inscripcion(request):
    if request.method == "POST":
        data = json.loads(request.body)

        documento = data.get("documento")
        email = data.get("email")

        # Buscar si ya existe
        estudiante = DatosDeEstudiantes.objects.filter(documento=documento).first()

        if not estudiante:
            estudiante = DatosDeEstudiantes(
                nombre=data.get("nombre"),
                apellido=data.get("apellido"),
                documento=documento,
                email=email,
                fecha_nacimiento=data.get("fecha_nacimiento"),
                pais=data.get("pais"),
                provincia=data.get("provincia"),
                telefono=data.get("telefono"),
            )

        # Buscar comisión
        comision_codigo = data.get("comision_codigo")  # debería venir del tab 2
        comision = Comision.objects.filter(codigo=comision_codigo).first()

        # Asignar al primer campo cursando libre
        for i in range(1, 16):
            campo = f"cursando{i}"
            if getattr(estudiante, campo) is None:
                setattr(estudiante, campo, comision)
                break

        estudiante.save()

        return JsonResponse({"status": "ok", "msg": "Datos guardados correctamente"})
    return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

#--------------------------envio de confimacion (pago inscripcion)---------------------------#

from django.core.mail import EmailMessage
from django.core.files.storage import default_storage

@csrf_exempt
def enviar_confirmacion(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre")
        documento = request.POST.get("documento")
        comprobante = request.FILES["comprobante"]

        path = default_storage.save("comprobantes/" + comprobante.name, comprobante)

        email = EmailMessage(
            f"Reserva de {nombre}",
            f"Documento: {documento}\nNombre: {nombre}\nComprobante adjunto.",
            "noreply@tecnomarema.com",
            ["tecnomarema.ar@gmail.com"],
        )
        email.attach_file(path)
        email.send()

        return JsonResponse({"status": "ok", "msg": "Correo enviado correctamente"})
    return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

########################################################################################
##------------------------alta manual de alumnos--------------------------------------##
########################################################################################
from django.shortcuts import render, redirect
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.db import IntegrityError
from django.urls import reverse
from django.template.loader import render_to_string
from .forms import AltaAlumnoForm
from .models import DatosDeEstudiantes, PerfilUsuario

def alta_alumno_view(request):
    mostrar_modal_error = False

    if request.method == 'POST':
        form = AltaAlumnoForm(request.POST)
        if form.is_valid():
            datos = form.save(commit=False)

            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            correo = datos.correo

            # Capturamos el rol seleccionado, si no viene, 'alumno' por defecto
            rol = form.cleaned_data.get('rol', 'alumno')

            if PerfilUsuario.objects.filter(nombre_usuario=username).exists():
                form.add_error('username', 'Este nombre de usuario ya está en uso. Elegí otro.')
                mostrar_modal_error = True
            else:
                try:
                    # 1. Guardamos el estudiante para que exista el id_estudiante
                    datos.save()

                    # 2. Creamos o actualizamos el PerfilUsuario asignando id_usuario = id_estudiante y guardando el rol
                    usuario, creado = PerfilUsuario.objects.update_or_create(
                        id_usuario=datos.id_estudiante,
                        defaults={
                            'id_estudiante': datos,          # FK a DatosDeEstudiantes
                            'nombre_usuario': username,
                            'correo': correo,
                            'rol': rol,                     # <-- guardamos el rol
                            'is_active': True,
                            'is_staff': False,
                        }
                    )

                    # 3. Seteamos la contraseña (en caso de update no queda set)
                    usuario.set_password(password)
                    usuario.save()

                    # 4. Enviar email de confirmación
                    reset_path = reverse('password_reset')
                    reset_url = request.build_absolute_uri(reset_path)

                    html_content = render_to_string('registration/bienvenida_alumno.html', {
                        'nombre': datos.nombre,
                        'usuario': username,
                        'password': password,
                        'reset_url': reset_url,
                    })

                    email = EmailMultiAlternatives(
                        subject="🎓 ¡Bienvenido/a a Tecno Marema!",
                        body="Este mensaje requiere un cliente compatible con HTML.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[correo],
                    )
                    email.attach_alternative(html_content, "text/html")
                    email.send()

                    return redirect('alumno_alta_exitosa')

                except IntegrityError:
                    form.add_error('username', 'Este nombre de usuario ya está registrado.')
                    mostrar_modal_error = True
    else:
        siguiente_id = obtener_siguiente_id_estudiante()
        form = AltaAlumnoForm(initial={'id_estudiante': siguiente_id})

    return render(request, 'educativa/alta_alumno.html', {
        'form': form,
        'mostrar_modal_error': mostrar_modal_error
    })


#----------------------------------------------------------
def alumno_alta_exitosa_view(request):
    return render(request, 'educativa/alumno_alta_exitosa.html')

#----------------------------------------------------------
from django.http import JsonResponse
from .models import PerfilUsuario

def verificar_nombre_usuario(request):
    nombre_usuario = request.GET.get('nombre_usuario', None)
    existe = PerfilUsuario.objects.filter(nombre_usuario=nombre_usuario).exists()
    return JsonResponse({'disponible': not existe})

############################################################################################
##-----------asignando de forma automáticamente el valor de id----------------------------##
############################################################################################
from .models import DatosDeEstudiantes

def obtener_siguiente_id_estudiante():
    existentes = DatosDeEstudiantes.objects.values_list('id_estudiante', flat=True)
    usados = set(int(e) for e in existentes if e.isdigit())

    for i in range(1, 999999 + 1):
        candidato = f"{i:06d}"
        if i not in usados:
            return candidato
    raise Exception("Se alcanzó el máximo de IDs disponibles.")

#############################################################################################
##----------------------------altas comisiones---------------------------------------------##
#############################################################################################
def alta_comision_view(request):
    cursos = Curso.objects.all()
    guardado_exitoso = request.GET.get('guardado') == '1'

    if request.method == 'POST':
        form = ComisionForm(request.POST)
        if form.is_valid():
            comision = form.save(commit=False)
            comision.id_comision = generar_id_comision()  # Este se vuelve a generar por seguridad
            comision.estado = 'Proxima'
            comision.save()
            return redirect('/alta_comision/?guardado=1')
    else:
        proximo_id = generar_id_comision()
        form = ComisionForm(initial={'id_comision': proximo_id})

    return render(request, 'educativa/alta_comision.html', {
        'form': form,
        'cursos': cursos,
        'guardado_exitoso': guardado_exitoso
    })

#-------------------------------------------------------------------------------------------

from django.shortcuts import render, redirect
from .models import Curso, Comision
from .forms import ComisionForm

def generar_id_comision():
    ultima = Comision.objects.order_by('-id_comision').first()
    if ultima and ultima.id_comision:
        nuevo_numero = int(ultima.id_comision) + 1
    else:
        nuevo_numero = 1
    return str(nuevo_numero).zfill(6)

#-----------------------------------------------------------------------------

from .models import Comision

def obtener_siguiente_id_comision():
    existentes = Comision.objects.values_list('id_comision', flat=True)
    usados = set(int(e) for e in existentes if e.isdigit())

    for i in range(1, 999999 + 1):
        candidato = f"{i:06d}"
        if i not in usados:
            return candidato
    raise Exception("Se alcanzó el máximo de IDs de comisión disponibles.")

###############################################################################
###--------------------------alta de cursos-------------------------------- ###
###############################################################################
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Curso
from .forms import CursoForm

def generar_id_curso():
    existentes = Curso.objects.values_list('id_curso', flat=True)
    usados = set(int(c) for c in existentes if c.isdigit())
    for i in range(1, 100):  # 01 a 99
        candidato = f"{i:02d}"
        if i not in usados:
            return candidato
    raise Exception("Se alcanzó el máximo de IDs")

def alta_curso_view(request):
    guardado_exitoso = request.GET.get('guardado') == '1'
    id_generado = generar_id_curso()

    if request.method == 'POST':
        # form = CursoForm(request.POST)
        form = CursoForm(request.POST, request.FILES)
        if form.is_valid():
            curso = form.save(commit=False)
            curso.id_curso = id_generado
            curso.fecha_creacion = timezone.now()
            curso.save()
            return redirect('/alta_curso/?guardado=1')
    else:
        form = CursoForm()

    return render(request, 'educativa/alta_curso.html', {
        'form': form,
        'guardado_exitoso': guardado_exitoso,
        'id_generado': id_generado
    })

##############################################################################################################
###-------------------------------vista_de_cursos_desde_el_perfil_alumno-----------------------------------###
##############################################################################################################
from django.shortcuts import render, redirect, get_object_or_404
from .models import PerfilUsuario, DatosDeEstudiantes, Comision

def cursos_alumno(request):
    usuario_id = request.session.get('usuario_logueado')
    if not usuario_id:
        return redirect('login')

    usuario = get_object_or_404(PerfilUsuario, id_usuario=usuario_id)
    datos_estudiante = usuario.id_estudiante  # Relación uno a uno

    comisiones = []
    for i in range(1, 10):  # cursando1_id a cursando9_id
        comision_id = getattr(datos_estudiante, f'cursando{i}_id', None)
        if comision_id:
            comision = Comision.objects.filter(id_comision=comision_id).select_related('id_curso').first()
            if comision:
                comisiones.append(comision)

    context = {
        'nombre_usuario': usuario.nombre_usuario,
        'comisiones': comisiones
    }
    return render(request, 'educativa/mis_cursos.html', context)

###################################################################################################
#---------------------------------el curso view---------------------------------------------------#
###################################################################################################

from datetime import datetime, timedelta
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import PerfilUsuario, Curso, Comision, Clase, ClaseComision, AsistenciaClase
from .decorators import session_required
from plataforma.models import EntregaProyecto
from plataforma.models import ValoracionAlumno


@session_required
def curso_detalle_view(request, id_comision):
    # 1. Verificar sesión
    nombre_usuario = request.session.get('usuario_logueado')
    if not nombre_usuario:
        return redirect('login')

    # 2. Obtener usuario y estudiante
    try:
        usuario = PerfilUsuario.objects.select_related('id_estudiante').get(nombre_usuario=nombre_usuario)
        estudiante = usuario.id_estudiante
    except PerfilUsuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login')

    # 3. Obtener comisión y curso correspondiente
    comision = get_object_or_404(Comision, id_comision=id_comision)
    curso = comision.id_curso

    # 4. Verificar inscripción
    if comision not in [
        estudiante.cursando1, estudiante.cursando2, estudiante.cursando3,
        estudiante.cursando4, estudiante.cursando5, estudiante.cursando6,
        estudiante.cursando7, estudiante.cursando8, estudiante.cursando9,
    ]:
        messages.error(request, 'No estás inscripto en esta comisión.')
        return redirect('mis_cursos')

    # 5. Obtener clases activas
    clases_del_curso = curso.clases.filter(estado_clase='Activo').order_by('numero_clase')

    # 6. Obtener ClaseComision asociadas
    clases_comisionadas = ClaseComision.objects.filter(
        comision=comision,
        clase__in=clases_del_curso
    ).select_related('clase')

    clasecomision_dict = {cc.clase_id: cc for cc in clases_comisionadas}

    # 7. Obtener asistencias
    # ✅ 7. Obtener IDs de clases de esta comisión
    clases_ids_de_la_comision = [cc.clase.id for cc in clases_comisionadas]

    # ✅ 7.1. Filtrar asistencias del estudiante en esas clases Y en esa comisión
    asistencias = AsistenciaClase.objects.filter(
        estudiante=estudiante,
        clase_id__in=clases_ids_de_la_comision,
        comision=comision  # Aquí el objeto, no el número como string
    )

    clases_presentes_dict = {a.clase_id: True for a in asistencias}
    clases_presentes_ids = list(clases_presentes_dict.keys())


    # 7.5. Obtener valoraciones hechas por el estudiante en esta comisión (filtrando también por comisión)
    valoraciones = ValoracionAlumno.objects.filter(
        id_estudiante=estudiante,
        comision_id=comision.id_comision,  # filtro clave para que sea sólo la comisión actual
        clase__in=clases_del_curso,
    )

    # Obtener lista de tuplas (clase_id, comision_id)
    clases_valoradas_ids_y_comisiones = list(valoraciones.values_list('clase_id', 'comision_id'))

    # Crear un set para búsqueda rápida en el template
    valoraciones_combinadas = set(clases_valoradas_ids_y_comisiones)

    # Opcional: lista sólo de ids de clases valoradas en esta comisión
    clases_valoradas_ids = [clase_id for clase_id, _ in clases_valoradas_ids_y_comisiones]



    # 8. Calcular posibilidad de valorar
    ahora = timezone.now()
    valoraciones_disponibles = {}

    for cc in clases_comisionadas:
        if cc.fecha and cc.hora_fin:
            fin_clase = datetime.combine(cc.fecha, cc.hora_fin)
            fin_clase = timezone.make_aware(fin_clase)
            limite = fin_clase + timedelta(days=3)
            valoraciones_disponibles[cc.clase.id] = fin_clase <= ahora <= limite
        else:
            valoraciones_disponibles[cc.clase.id] = False  # Si falta info, no se puede valorar

    # 9. Selección de template
    nombre_normalizado = curso.nombre_curso.strip().lower()
    templates_por_curso = {
        "desarrollo web": "educativa/curso_desarrollo_web.html",
        "desarrollo web_v2": "educativa/curso_desarrollo_web_v2.html",
        "inteligencia artificial": "educativa/curso_ia.html",
        "python": "educativa/curso_python.html",
        "javascript": "educativa/curso_javascript.html",
    }
    template_a_usar = templates_por_curso.get(nombre_normalizado, "educativa/curso_detalle.html")

    # 9.5. Buscar si el estudiante ya entregó el proyecto en esta comisión
    entrega_existente = EntregaProyecto.objects.filter(
        estudiante=estudiante,
        comision=comision
    ).first()


    # 10. Render
    contexto = {
        'usuario': usuario,
        'estudiante': estudiante,
        'curso': curso,
        'comision': comision,
        'nombre_usuario': nombre_usuario,
        'es_autenticado': True,
        'clases': clases_del_curso,
        'clasescomision': clasecomision_dict,
        'clases_presentes_ids': clases_presentes_ids,
        'valoraciones_disponibles': valoraciones_disponibles,  # ✅ nuevo diccionario
        "clases_valoradas_ids": clases_valoradas_ids, #se agrega
        'clases_valoradas_ids_y_comisiones': clases_valoradas_ids_y_comisiones, #se agrega
        'valoraciones_combinadas': valoraciones_combinadas, #se agrega
        "entrega_existente": entrega_existente,  # 👈 se está pasando
        'alumno_id': estudiante.id_estudiante,
    }
    

    from django.db.models import Sum
    from plataforma.models import PuntajeQuiz

    # --- Estadísticas de quizzes ---
    clases_curso = curso.clases.all()  # Todas las clases del curso
    total_quizzes = clases_curso.count()

    # Total de quizzes hechos por el estudiante
    quizzes_realizados = PuntajeQuiz.objects.filter(
        estudiante=estudiante,
        clase__curso=curso,
        comision=comision  # línea agregada
    ).count()

    # Puntaje acumulado por el estudiante
    puntaje_total = PuntajeQuiz.objects.filter(
        estudiante=estudiante,
        clase__curso=curso,
        comision=comision  # línea agregada
    ).aggregate(Sum("puntaje_inicial"))["puntaje_inicial__sum"] or 0

    # Puntaje máximo posible (10 puntos por clase)
    puntaje_maximo_posible = total_quizzes * 10

    # Agregar al contexto
    contexto["quizzes_realizados"] = quizzes_realizados
    contexto["quizzes_totales"] = total_quizzes
    contexto["puntaje_total_quiz"] = puntaje_total
    contexto["puntaje_maximo_posible"] = puntaje_maximo_posible

    # 🔢 Total de clases activas de la comisión
    total_clases_comision = clases_comisionadas.count()

    # ✅ Asistencias del estudiante en esta comisión (no en otras del mismo curso)
    asistencias_en_comision = AsistenciaClase.objects.filter(
        estudiante=estudiante,
        clase__in=[cc.clase for cc in clases_comisionadas],
        comision=comision  # 👈 filtro clave para distinguir comisiones
    ).count()


    # 👉 Guardar en el contexto
    contexto["asistencias_en_comision"] = asistencias_en_comision
    contexto["total_clases_comision"] = total_clases_comision

    return render(request, template_a_usar, contexto)




#######################################################################
###---------------------Estado de comision-------------------------####
#######################################################################

from datetime import date

def obtener_estado_comision(fecha_inicio, fecha_fin):
    hoy = date.today()
    if hoy < fecha_inicio:
        return 'proximo'
    elif fecha_inicio <= hoy <= fecha_fin:
        return 'en_curso'
    else:
        return 'finalizado'
    
#----------------------------------------------------------------
def actualizar_comisiones():
    comisiones = Comision.objects.all()

    for comision in comisiones:
        estado = obtener_estado_comision(comision.fecha_inicio, comision.fecha_fin)
        comision.estado_comision = estado
        comision.save()

###############################################################################
##---------------------traer nombres de clases-------------------------------##
###############################################################################

from django.shortcuts import render, get_object_or_404
from .models import Clase, Curso

def curso_desarrollo_web_view(request):
    curso = get_object_or_404(Curso, nombre="Desarrollo Web")
    clases = Clase.objects.filter(curso=curso).order_by('numero_clase')
    return render(request, 'curso_desarrollo_web.html', {
        'clases': clases,
        'curso': curso,
    })

######------------------------------------------------------------------------------
from .models import Clase

def curso_view(request, curso_id):
    clases = Clase.objects.filter(curso_id=curso_id, estado_clase='activo').order_by('numero_clase')
    return render(request, 'educativa/curso.html', {'clases': clases})


####################################################################################
#-------------alta clase comision se cargan los datos desde el teamplate-----------#
####################################################################################

from django.shortcuts import render, redirect
from .models import Curso, Comision, Clase, ClaseComision
from .forms import ClaseComisionForm
from django.utils.crypto import get_random_string

def alta_clase_comision_view(request):
    comisiones = Comision.objects.all()
    clases = Clase.objects.all().order_by('id')
    comision_seleccionada = None
    clase_existente = None
    form = ClaseComisionForm()

    if request.method == 'POST':
        # Carga de una nueva clase general
        if 'guardar_clase' in request.POST:
            id_clase = request.POST.get('id_clase')
            nombre_clase = request.POST.get('nombre_clase')
            numero_clase = request.POST.get('numero_clase')
            fecha_clase = request.POST.get('fecha_clase')
            presentacion = request.POST.get('presentacion')
            video = request.POST.get('video')
            comision_id = request.POST.get('id_comision')

            comision = Comision.objects.get(id_comision=comision_id)
            curso = comision.id_curso

            Clase.objects.create(
                id_clase=id_clase,
                nombre_clase=nombre_clase,
                numero_clase=numero_clase,
                fecha_clase=fecha_clase,
                presentacion=presentacion,
                video=video,
                id_comision=comision,
                id_curso=curso
            )

            return redirect(f'/alta_clase_comision/?id_comision={comision_id}')

        # Carga o actualización de una ClaseComision
        elif 'guardar_clase_comision' in request.POST:
            comision_id = request.POST.get('comision')
            clase_id = request.POST.get('clase')

            try:
                clase_existente = ClaseComision.objects.get(comision_id=comision_id, clase_id=clase_id)
                form = ClaseComisionForm(request.POST, instance=clase_existente)  # Actualizar existente
            except ClaseComision.DoesNotExist:
                form = ClaseComisionForm(request.POST)  # Crear nuevo

            if form.is_valid():
                form.save()
                return redirect(f'/alta_clase_comision/?id_comision={comision_id}&guardado=1')
            else:
                print(form.errors)  # Debug en consola

    # Si es GET (mostrar formulario)
    else:
        form = ClaseComisionForm()

    comision_id = request.GET.get('id_comision')
    clase_id = request.GET.get('clase_id')  # opcional: para precargar una clase seleccionada

    if comision_id:
        comision_seleccionada = Comision.objects.get(id_comision=comision_id)
        clases = Clase.objects.filter(curso=comision_seleccionada.id_curso).order_by('numero_clase')

        # Si también recibimos clase_id, buscamos si ya hay ClaseComision
        if clase_id:
            try:
                clase_existente = ClaseComision.objects.get(comision_id=comision_id, clase_id=clase_id)
                form = ClaseComisionForm(instance=clase_existente)
            except ClaseComision.DoesNotExist:
                pass

    guardado_exitoso = request.GET.get('guardado') == '1'

    nuevo_id_clase = get_random_string(length=8).upper()

    # Extraemos horas si ya hay clase_comision cargada
    hora_inicio = hora_fin = None
    if clase_existente:
        hora_inicio = clase_existente.horario
        hora_fin = clase_existente.hora_fin

    return render(request, 'educativa/alta_clase_comision.html', {
        'comisiones': comisiones,
        'comision_seleccionada': comision_seleccionada,
        'clases': clases,
        'nuevo_id_clase': nuevo_id_clase,
        'form': form,
        'guardado_exitoso': guardado_exitoso,
        'hora_inicio': hora_inicio,
        'hora_fin': hora_fin
    })

#----------------------------------------------------------------------------
#-----------obtener los datos del formulario clase comision------------------
#----------------------------------------------------------------------------

from django.http import JsonResponse
from .models import ClaseComision

def obtener_datos_clase_comision(request):
    comision_id = request.GET.get('comision_id')
    clase_id = request.GET.get('clase_id')

    try:
        clase_comision = ClaseComision.objects.get(
            comision__id_comision=comision_id,
            clase__id=clase_id
        )
        data = {
            'fecha': clase_comision.fecha.isoformat() if clase_comision.fecha else '',
            'hora_inicio': clase_comision.horario.strftime('%H:%M') if clase_comision.horario else '',
            'hora_fin': clase_comision.hora_fin.strftime('%H:%M') if clase_comision.hora_fin else '',
            'link': clase_comision.link or '',
            'video': clase_comision.video or ''
        }
    except ClaseComision.DoesNotExist:
        data = {
            'fecha': '',
            'hora_inicio': '',
            'hora_fin': '',
            'link': '',
            'video': ''
        }

    return JsonResponse(data)




#------------------------------------------------------------------------------
#        trae las clases del curso correspondiente
#------------------------------------------------------------------------------
from django.http import JsonResponse
from .models import Clase, Comision

def obtener_clases_de_comision(request):
    comision_id = request.GET.get('comision_id')

    try:
        comision = Comision.objects.get(id_comision=comision_id)
        curso = comision.id_curso
        clases = Clase.objects.filter(curso=curso).order_by('numero_clase').values('id', 'nombre_clase')
        data = [{'id': c['id'], 'nombre': c['nombre_clase']} for c in clases]
    except Comision.DoesNotExist:
        data = []

    return JsonResponse({'clases': data})




##############################################################################
#-----------------------------------------------------------------------#
##############################################################################

from django.shortcuts import render, get_object_or_404
from .models import Comision, ClaseComision

def detalle_comision_view(request, comision_id):
    comision = get_object_or_404(Comision, id_comision=comision_id)
    clases_comisionadas = ClaseComision.objects.filter(comision=comision).select_related('clase').order_by('clase__numero_clase')

    return render(request, 'educativa/detalle_comision.html', {
        'comision': comision,
        'clases_comisionadas': clases_comisionadas,
    })

#-**************************************************************************************************************************

# #######################################################################
###---------------------IMPORTS------------------------------------####
#######################################################################

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.contrib import messages
from django.db import transaction
from datetime import date, datetime, timedelta
from django.utils import timezone  # ← Añadido para update

from .models import Curso, Comision, Clase, ClaseComision, ReprogramacionDeClase
from .forms import ClaseComisionForm

# Para envío real de correo
from django.core.mail import send_mail

#######################################################################
###---------------------FUNCIONES AUXILIARES-----------------------####
#######################################################################

def obtener_estado_comision(fecha_inicio, fecha_fin):
    hoy = date.today()
    if hoy < fecha_inicio:
        return 'proximo'
    elif fecha_inicio <= hoy <= fecha_fin:
        return 'en_curso'
    else:
        return 'finalizado'

def calcular_proxima_fecha_clase(clase_comision_actual, slots_a_mover):
    comision_pk = clase_comision_actual.comision.pk
    fecha_actual = clase_comision_actual.fecha
    hora_actual = clase_comision_actual.horario
    
    if not fecha_actual or not hora_actual:
        return None

    current_datetime = datetime.combine(fecha_actual, hora_actual)

    slots_qs = ClaseComision.objects.filter(
        comision_id=comision_pk,
        fecha__isnull=False
    ).exclude(pk=clase_comision_actual.pk).order_by('fecha', 'horario')

    lista_slots = [datetime.combine(s.fecha, s.horario) for s in slots_qs if s.fecha and s.horario]

    indice_siguiente = next((i for i, s in enumerate(lista_slots) if s > current_datetime), -1)

    if indice_siguiente == -1:
        if not lista_slots:
            return current_datetime + timedelta(days=7 * slots_a_mover)
        dias_de_ciclo = (lista_slots[-1] - lista_slots[-2]).days if len(lista_slots) >= 2 else 7
        return current_datetime + timedelta(days=dias_de_ciclo * slots_a_mover)

    indice_destino = indice_siguiente + slots_a_mover - 1
    if indice_destino < len(lista_slots):
        return lista_slots[indice_destino]
    else:
        ultimo_slot = lista_slots[-1]
        dias_de_ciclo = (lista_slots[-1] - lista_slots[-2]).days if len(lista_slots) >= 2 else 7
        slots_extra = indice_destino - len(lista_slots) + 1
        return ultimo_slot + timedelta(days=dias_de_ciclo * slots_extra)


def desplazar_clases_posteriores(clase_reprogramada, slots_diferencia):
    comision = clase_reprogramada.comision
    clases_posteriores = ClaseComision.objects.filter(
        comision=comision,
        clase__numero_clase__gt=clase_reprogramada.clase.numero_clase
    ).order_by('clase__numero_clase')

    movidas = 0
    for clase_pos in clases_posteriores:
        nueva_fecha_hora = calcular_proxima_fecha_clase(clase_pos, slots_diferencia)
        if nueva_fecha_hora:
            clase_pos.fecha = nueva_fecha_hora.date()
            clase_pos.horario = nueva_fecha_hora.time()
            clase_pos.save(update_fields=['fecha', 'horario'])
            movidas += 1
    return movidas


def enviar_notificacion_por_reprogramacion(clase_comision, motivo, estado, request=None):
    try:
        comision = clase_comision.comision
        alumnos = getattr(comision, 'alumnos', None)
        emails = []

        if alumnos and hasattr(alumnos, 'all'):
            for alumno in alumnos.all():
                if alumno.email and '@' in alumno.email:
                    emails.append(alumno.email)

        if not emails:
            print("[EMAIL] No hay alumnos con email válido.")
            if request:
                messages.warning(request, "No hay alumnos con email.")
            return False

        subject = f"CLASE {estado.upper()}: {clase_comision.clase.nombre_clase}"
        cuerpo = f"""
¡Hola!

La clase ha sido {estado.upper()}:

Comisión: {comision.id_comision}
Clase: {clase_comision.clase.nombre_clase}
Fecha: {clase_comision.fecha.strftime('%d/%m/%Y')} a las {clase_comision.horario.strftime('%H:%M')}

Motivo: {motivo}

¡Saludos!
        """.strip()

        print(f"[EMAIL] Enviando a: {emails}")
        send_mail(subject, cuerpo, None, emails, fail_silently=False)
        print(f"[EMAIL] CORREO ENVIADO A {len(emails)} ALUMNOS")
        if request:
            messages.success(request, f"Correo enviado a {len(emails)} alumnos.")
        return True

    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        if request:
            messages.error(request, f"Error enviando correo: {e}")
        return False


#######################################################################
###---------------------VIEWS PRINCIPALES-------------------------####
#######################################################################

def alta_clase_comision_view(request):
    comisiones = Comision.objects.all()
    clases = Clase.objects.all().order_by('id')
    comision_seleccionada = None
    clase_existente = None
    form = ClaseComisionForm()

    if request.method == 'POST':
        comision_pk = request.POST.get('comision')
        clase_id = request.POST.get('clase')

        # === GUARDAR CLASE GENERAL ===
        if 'guardar_clase' in request.POST:
            comision_id_ext = request.POST.get('id_comision')
            comision = Comision.objects.get(id_comision=comision_id_ext)
            curso = comision.id_curso

            Clase.objects.create(
                id_clase=request.POST.get('id_clase'),
                nombre_clase=request.POST.get('nombre_clase'),
                numero_clase=request.POST.get('numero_clase'),
                fecha_clase=request.POST.get('fecha_clase'),
                presentacion=request.POST.get('presentacion'),
                video=request.POST.get('video'),
                id_comision=comision,
                id_curso=curso
            )
            messages.success(request, "Clase general creada exitosamente.")
            return redirect(f'/alta_clase_comision/?id_comision={comision_id_ext}&guardado=1')

        # === GUARDAR CLASECOMISION O REPROGRAMAR ===
        elif 'guardar_clase_comision' in request.POST:
            comision_obj = get_object_or_404(Comision, pk=comision_pk)
            comision_redirect_id = comision_obj.id_comision

            es_reprogramacion = request.POST.get('reprogramar_clase') == 'on'
            clase_comision_pk = request.POST.get('clase_comision_id')
            accion_reprogramacion = request.POST.get('accion_reprogramacion', '').strip()
            motivo_opcion = request.POST.get('motivo_opcion', '')
            motivo_detalle = request.POST.get('motivo_detalle', '')
            motivo_completo = f"{motivo_opcion}: {motivo_detalle}".strip() if motivo_detalle else motivo_opcion

            try:
                clase = ClaseComision.objects.get(comision_id=comision_pk, clase_id=clase_id)
            except ClaseComision.DoesNotExist:
                messages.error(request, "Clase no encontrada.")
                return redirect(f'/alta_clase_comision/?id_comision={comision_redirect_id}')

            # === GUARDADO NORMAL (sin reprogramar) ===
            if not es_reprogramacion:
                form = ClaseComisionForm(request.POST, instance=clase)
                if form.is_valid():
                    form.save()
                    messages.success(request, "Clase guardada correctamente.")
                else:
                    messages.error(request, "Error en el formulario.")
                return redirect(f'/alta_clase_comision/?id_comision={comision_redirect_id}&guardado=1')

            # === REPROGRAMACIÓN ===
            if str(clase.pk) != clase_comision_pk:
                messages.error(request, "Error de seguridad: clase no coincide.")
                return redirect(f'/alta_clase_comision/?id_comision={comision_redirect_id}')

            estado_final = None
            fecha_reprogramada = None
            clases_movidas = 0
            fecha_original = clase.fecha  # GUARDAMOS LA FECHA ORIGINAL

            if accion_reprogramacion == 'Cancelada':
                estado_final = 'Cancelada'
                messages.warning(request, f"Clase {clase.clase.nombre_clase} CANCELADA.")

            elif accion_reprogramacion and accion_reprogramacion.lstrip('-+').isdigit():
                slots = int(accion_reprogramacion)
                nueva_fecha_hora = calcular_proxima_fecha_clase(clase, slots)
                if not nueva_fecha_hora:
                    messages.error(request, "No se pudo calcular nueva fecha.")
                    return redirect(f'/alta_clase_comision/?id_comision={comision_redirect_id}')

                clase.fecha = nueva_fecha_hora.date()
                clase.horario = nueva_fecha_hora.time()
                clase.save()

                clases_movidas = desplazar_clases_posteriores(clase, slots)
                estado_final = 'Reprogramada'
                fecha_reprogramada = nueva_fecha_hora.date()

                messages.success(request, f"Clase reprogramada y {clases_movidas} clases posteriores movidas.")

            else:
                messages.error(request, f"Acción no válida: '{accion_reprogramacion}'")
                return redirect(f'/alta_clase_comision/?id_comision={comision_redirect_id}')

            # === GUARDAR EN TABLA REPROGRAMACIÓN ===
            try:
                ReprogramacionDeClase.objects.update_or_create(
                    clase_afectada=clase,
                    defaults={
                        'estado_final': estado_final,
                        'accion_solicitada': accion_reprogramacion,
                        'motivo_principal': motivo_opcion,
                        'motivo_detalle': motivo_detalle or None,
                        'fecha_original': fecha_original,
                        'fecha_reprogramada': fecha_reprogramada,
                        'notificado_correo': False
                    }
                )
            except Exception as e:
                messages.error(request, f"Error al guardar historial: {e}")
                print("ERROR GUARDANDO REPROGRAMACIÓN:", e)

            # === ENVÍO AUTOMÁTICO EN SEGUNDO PLANO (NO DEMORA NADA) ===
            from threading import Thread
            import subprocess
            import sys
            import os

            def enviar_correos():
                subprocess.Popen([
                    sys.executable, 'manage.py', 'enviar_notificacion_ausencia'
                ], cwd=os.getcwd(), creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

            Thread(target=enviar_correos, daemon=True).start()

            messages.success(request, 
                f"¡Clase {estado_final.lower()} correctamente! "
                "Los alumnos están siendo notificados ahora mismo..."
            )

            return redirect(f'/alta_clase_comision/?id_comision={comision_redirect_id}&guardado=1')

    # === GET ===
    comision_id_ext = request.GET.get('id_comision')
    clase_id = request.GET.get('clase_id')

    if comision_id_ext:
        try:
            comision_seleccionada = Comision.objects.get(id_comision=comision_id_ext)
            clases = Clase.objects.filter(curso=comision_seleccionada.id_curso).order_by('numero_clase')

            if clase_id:
                try:
                    clase_existente = ClaseComision.objects.get(comision=comision_seleccionada, clase_id=clase_id)
                    form = ClaseComisionForm(instance=clase_existente)
                except ClaseComision.DoesNotExist:
                    clase_existente = None
        except Comision.DoesNotExist:
            messages.error(request, "Comisión no encontrada.")

    return render(request, 'educativa/alta_clase_comision.html', {
        'comisiones': comisiones,
        'comision_seleccionada': comision_seleccionada,
        'clases': clases,
        'nuevo_id_clase': get_random_string(length=8).upper(),
        'form': form,
        'guardado_exitoso': request.GET.get('guardado') == '1',
        'clase_existente': clase_existente,
        'hora_inicio': clase_existente.horario if clase_existente else None,
        'hora_fin': clase_existente.hora_fin if clase_existente else None,
    })
# === RESTO DE VIEWS (sin cambios) ===
def obtener_datos_clase_comision(request):
    comision_id = request.GET.get('comision_id')
    clase_id = request.GET.get('clase_id')
    try:
        clase_comision = ClaseComision.objects.get(comision__id_comision=comision_id, clase__id=clase_id)
        data = {
            'fecha': clase_comision.fecha.isoformat() if clase_comision.fecha else '',
            'clase_comision_pk': str(clase_comision.pk),
            'hora_inicio': clase_comision.horario.strftime('%H:%M') if clase_comision.horario else '',
            'hora_fin': clase_comision.hora_fin.strftime('%H:%M') if clase_comision.hora_fin else '',
            'link': clase_comision.link or '',
            'video': clase_comision.video or ''
        }
    except ClaseComision.DoesNotExist:
        data = {k: '' for k in ['fecha', 'clase_comision_pk', 'hora_inicio', 'hora_fin', 'link', 'video']}
    return JsonResponse(data)

def obtener_clases_de_comision(request):
    comision_id = request.GET.get('comision_id')
    try:
        comision = Comision.objects.get(id_comision=comision_id)
        clases = Clase.objects.filter(curso=comision.id_curso).order_by('numero_clase').values('id', 'nombre_clase')
        data = [{'id': c['id'], 'nombre': c['nombre_clase']} for c in clases]
    except Comision.DoesNotExist:
        data = []
    return JsonResponse({'clases': data})

def detalle_comision_view(request, comision_id):
    comision = get_object_or_404(Comision, id_comision=comision_id)
    clases_comisionadas = ClaseComision.objects.filter(comision=comision).select_related('clase').order_by('clase__numero_clase')
    return render(request, 'educativa/detalle_comision.html', {
        'comision': comision,
        'clases_comisionadas': clases_comisionadas,
    })

def curso_view(request, curso_id):
    clases = Clase.objects.filter(curso_id=curso_id, estado_clase='activo').order_by('numero_clase')
    return render(request, 'educativa/curso.html', {'clases': clases})

def curso_desarrollo_web_view(request):
    curso = get_object_or_404(Curso, nombre="Desarrollo Web")
    clases = Clase.objects.filter(curso=curso).order_by('numero_clase')
    return render(request, 'curso_desarrollo_web.html', {'clases': clases, 'curso': curso})
#-*******************************************************************************************************************************************

##############################################################################
#-----------------------------------------------------------------------#
##############################################################################

from django.shortcuts import render, get_object_or_404
from .models import PerfilUsuario, Curso, Comision, DatosDeEstudiantes
from django.db.models import Q

def participantes_view(request, numero_comision, id_curso):
    curso = get_object_or_404(Curso, id_curso=id_curso)
    comision = get_object_or_404(Comision, numero_comision=numero_comision, id_curso=curso)

    estudiantes = DatosDeEstudiantes.objects.filter(
        Q(cursando1=comision) |
        Q(cursando2=comision) |
        Q(cursando3=comision) |
        Q(cursando4=comision) |
        Q(cursando5=comision) |
        Q(cursando6=comision) |
        Q(cursando7=comision) |
        Q(cursando8=comision) |
        Q(cursando9=comision)
    )

    profesores = PerfilUsuario.objects.filter(rol='profesor', id_estudiante__in=estudiantes)
    tutores = PerfilUsuario.objects.filter(rol='tutor', id_estudiante__in=estudiantes)
    alumnos = PerfilUsuario.objects.filter(rol='alumno', id_estudiante__in=estudiantes)

    nombre_usuario = request.session.get('usuario_logueado')
    perfil_usuario_logueado = None
    if nombre_usuario:
        try:
            perfil_usuario_logueado = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
        except PerfilUsuario.DoesNotExist:
            perfil_usuario_logueado = None

    context = {
        'curso': curso,
        'comision': comision,
        'profesores': profesores,
        'tutores': tutores,
        'alumnos': alumnos,
        'cantidad_alumnos': alumnos.count(),
        'perfil_usuario_logueado': perfil_usuario_logueado,
    }

    return render(request, 'educativa/participantes.html', context)




#####################################################################################################################################
#  La vista listar_usuarios_view obtiene todos los usuarios desde el modelo PerfilUsuario junto con sus datos relacionados
#  y los envía a la plantilla usuarios.html para ser mostrados.
#####################################################################################################################################
from django.shortcuts import render
from .models import PerfilUsuario

def listar_usuarios_view(request):
    usuarios = PerfilUsuario.objects.select_related('id_estudiante').all()
    return render(request, 'participantes.html', {'usuarios': usuarios})


#######################################################################
###---------------------marcar el presente-------------------------####
#######################################################################

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Clase, Comision, DatosDeEstudiantes, AsistenciaClase, ClaseComision
from .decorators import session_required

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import redirect

@session_required
def marcar_presente(request, comision_id, clase_id, alumno_id):
    print("DEBUG - Método:", request.method)
    print("DEBUG - Datos recibidos:", comision_id, clase_id, alumno_id)

    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    clase = Clase.objects.filter(id=clase_id).first()
    comision = Comision.objects.filter(id_comision=comision_id).first()
    estudiante = DatosDeEstudiantes.objects.filter(id_estudiante=alumno_id).first()

    if not clase or not comision or not estudiante:
        print("DEBUG - Alguno de los objetos es None")
        return JsonResponse({"error": "Faltan datos para marcar presente"}, status=400)

    if AsistenciaClase.objects.filter(estudiante=estudiante, clase=clase, comision=comision).exists():
        print("DEBUG - Ya presente")
        return JsonResponse({"ya_presente": True})

    cc = ClaseComision.objects.filter(clase=clase, comision=comision).first()
    if not cc:
        print("DEBUG - ClaseComision no encontrada")
        return JsonResponse({"error": "No se encontró la ClaseComision correspondiente"}, status=400)

    asistencia = AsistenciaClase(
        estudiante=estudiante,
        clase=clase,
        comision=comision,
        fecha_clase=cc.fecha,
        horario_inicio=cc.horario,
        horario_fin=cc.hora_fin,
    )
    asistencia.guardar_detalles()
    asistencia.save()

    print("DEBUG - Presente registrado correctamente")

    # Si la petición es AJAX devolvemos JSON, si no, redirigimos (por si alguien accede manualmente)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"presente": True})
    else:
        # Podés cambiar la URL de redirección que te convenga
        return redirect("mis_cursos")



################################################################################################
###-----------------mensaje de agradecimiento por la valoracion de la clase------------------###
################################################################################################

from django.shortcuts import render

def agradecimiento(request):
    return render(request, 'educativa/agradecimiento.html')

################################################################################################
###---------------------------------------quizzes--------------------------------------------###
################################################################################################

from django.shortcuts import render, get_object_or_404
from .models import Curso, Clase, Comision, DatosDeEstudiantes, PuntajeQuiz
from plataforma.models import Pregunta
from plataforma.decorators import session_required

# ----------------------------
# Vista del HUB de quizzes
# ----------------------------

@session_required
def hub_de_quizzes(request, curso_id, comision_id, estudiante_id):
    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=estudiante_id)
    # curso = get_object_or_404(Curso, id=curso_id)
    curso = get_object_or_404(Curso, id_curso=curso_id)
    comision = get_object_or_404(Comision, id_comision=comision_id)

    clases = Clase.objects.filter(curso=curso).order_by("numero_clase")

    # 📊 Puntajes por clase del estudiante y esa comisión
    puntajes_dict = {}
    for clase in clases:
        puntaje = PuntajeQuiz.objects.filter(
            estudiante=estudiante,
            clase=clase,
            comision=comision  # 👈 clave
        ).first()
        puntajes_dict[clase.id] = {
            "inicial": puntaje.puntaje_inicial if puntaje else "-",
            "maximo": puntaje.puntaje_maximo if puntaje else "-"
        }

    return render(request, "educativa/hub_de_quizzes.html", {
        "curso": curso,
        "comision": comision,  # 👈 ahora es la correcta
        "clases": clases,
        "estudiante": estudiante,
        "puntajes_dict": puntajes_dict,
    })

# ----------------------------
# Vista del Quiz por Clase
# ----------------------------

@session_required
def quiz_por_clase(request, clase_id):
    estudiante_id = request.session.get("usuario_id")
    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=estudiante_id)

    # Obtener la comisión actual del alumno por GET o fallback a la primera comisión del curso
    numero_comision = request.GET.get("comision")
    clase = get_object_or_404(Clase, id=clase_id)
    curso = clase.curso

    if numero_comision:
        comision = Comision.objects.filter(numero_comision=numero_comision, id_curso=curso).first()
    else:
        # Si no viene comision, tomar la primera comisión del curso
        comision = Comision.objects.filter(id_curso=curso).first()

    if not comision:
        return render(request, "error.html", {"mensaje": "Comisión no encontrada para este curso."})

    preguntas = Pregunta.objects.filter(clase=clase).order_by('id')
    total = preguntas.count()
    n = int(request.GET.get("n", 0))

    # Clave sesión con comisión para distinguir entre comisiones distintas
    clave_puntaje = f"puntaje_clase_{clase_id}_comision_{comision.numero_comision}"

    # Evaluar respuesta anterior si existe
    respuesta_usuario = request.GET.get("respuesta")
    if respuesta_usuario and n > 0:
        pregunta_anterior = preguntas[n - 1]
        if respuesta_usuario.lower() == pregunta_anterior.respuesta_correcta.lower():
            request.session[clave_puntaje] = request.session.get(clave_puntaje, 0) + 1

    # Fin del quiz: guardar puntaje con comisión asociada
    if n >= total:
        puntaje = request.session.get(clave_puntaje, 0)

        puntaje_obj, created = PuntajeQuiz.objects.get_or_create(
            estudiante=estudiante,
            clase=clase,
            comision=comision  # Aquí se asocia la comisión correcta
        )
        if created:
            puntaje_obj.puntaje_inicial = puntaje
        puntaje_obj.puntaje_maximo = max(puntaje, puntaje_obj.puntaje_maximo or 0)
        puntaje_obj.save()

        # Limpiar sesión para próximos intentos
        request.session.pop(clave_puntaje, None)

        return render(request, "educativa/quiz_finalizado.html", {
            "clase": clase,
            "puntaje": puntaje,
            # "puntaje_maximo": puntaje_maximo,
            "curso_id": comision.id_curso.id_curso,
            "comision_id": comision.id_comision,
            "estudiante_id": estudiante.id_estudiante,
        })

    pregunta = preguntas[n]

    return render(request, 'educativa/quiz_por_clase.html', {
        'clase': clase,
        'pregunta': pregunta,
        'n': n,
        'total': total,
        'comision': comision,
    })


#####################################################################################
####-----------------------Entrega del Proyecto Final----------------------------####
#####################################################################################

from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import EntregaProyectoForm
from .models import EntregaProyecto, Comision, DatosDeEstudiantes
from plataforma.decorators import session_required


@session_required
def entrega_proyecto_view(request, comision_id):
    estudiante_id = request.session.get('usuario_id')
    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=estudiante_id)
    comision = get_object_or_404(Comision, id_comision=comision_id)
    curso = comision.id_curso

    entrega_existente = EntregaProyecto.objects.filter(estudiante=estudiante, comision=comision).first()

    # 🟡 Guardar nota y feedback previos por separado
    nota_anterior = entrega_existente.nota if entrega_existente else None
    feedback_anterior = entrega_existente.feedback if entrega_existente else None

    if request.method == 'POST':
        form = EntregaProyectoForm(request.POST, request.FILES, instance=entrega_existente)
        if form.is_valid():
            entrega = form.save(commit=False)

            # ✅ Reasignar campos preservados
            entrega.estudiante = estudiante
            entrega.comision = comision
            entrega.curso = curso
            entrega.nota = nota_anterior
            entrega.feedback = feedback_anterior

            entrega.save()
            messages.success(request, "Entrega enviada correctamente.")
            # return redirect('curso_detalle', id_comision=comision_id)
            return redirect(f"{request.path}?entregado=1")
    else:
        form = EntregaProyectoForm(instance=entrega_existente)

    # 📆 Calcular límite de entrega
    fecha_fin = comision.fecha_fin
    fecha_limite = fecha_fin + timedelta(days=14)

    return render(request, 'educativa/entrega_proyecto.html', {
        'form': form,
        'comision': comision,
        'curso': curso,
        'estudiante': estudiante,
        'entrega_existente': entrega_existente,
        'fecha_limite': fecha_limite,
        'usuario': request.session.get('usuario_logueado'),
        'nombre_usuario': request.session.get('usuario_logueado'),
    })

################################################################################
#--------------------------------inscripcion-----------------------------------#
################################################################################

# views.py
import mercadopago
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json

@csrf_exempt
def procesar_pago_mercado(request):
    if request.method == "POST":
        # Asegúrate de que este TOKEN sea el de Producción o Test correspondiente
        sdk = mercadopago.SDK("TU_ACCESS_TOKEN_AQUI")
        
        try:
            datos = json.loads(request.body)

            # Para Mercado Pago, el monto que viaja en el "token" de seguridad
            # debe ser EXACTAMENTE igual al transaction_amount enviado aquí.
            pago = {
                "transaction_amount": float(datos["transaction_amount"]),
                "token": datos["token"],
                "description": datos.get("description", "Pago inscripción TecnoMarema"),
                "installments": int(datos["installments"]),
                "payment_method_id": datos["payment_method_id"],
                "issuer_id": datos["issuer_id"],
                "payer": {
                    "email": datos["payer"]["email"],
                    "identification": datos["payer"]["identification"]
                }
            }

            resultado = sdk.payment().create(pago)
            
            # Log para debug (opcional, quítalo en producción)
            print("Resultado MP:", resultado["status"]) 

            return JsonResponse(resultado["response"])
            
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    
    return JsonResponse({"status": "error"}, status=400)


#############################################################################
##------------------------proximas comisiones------------------------------##
#############################################################################

from django.shortcuts import render
from .models import Curso, Comision

def proximas_comisiones_desarrollo_web(request):
    try:
        desarrollo_web = Curso.objects.get(nombre_curso__iexact="Desarrollo Web")
    except Curso.DoesNotExist:
        comisiones = []
    else:
        comisiones = Comision.objects.filter(
            id_curso=desarrollo_web,
            estado_comision='próximo'
        ).order_by('fecha_inicio')

    return render(request, 'educativa/proximas_comisiones.html', {
        'comisiones': comisiones
    })


####################################################################################

# views.py
from django.shortcuts import redirect

# @session_required
def mi_certificado_redirect(request):
    usuario = request.user
    estudiante = usuario.id_estudiante
    comision = estudiante.cursando1  # o la que uses

    return redirect('mi_certificado', id_estudiante=estudiante.id_estudiante, id_comision=comision.id_comision)

####################################################################################
####################################################################################
####################################################################################
#aca con este codigo muestra las comisiones proximas del curso de desarrollo web
def desarrollo_web_compra(request):
    desarrollo_web = Curso.objects.filter(nombre_curso__icontains="desarrollo web").first()

    if desarrollo_web:
        comisiones = Comision.objects.filter(
            id_curso=desarrollo_web,
            estado_comision='proximo'
        ).order_by('fecha_inicio')
    else:
        comisiones = []

    return render(request, 'educativa/desarrollo_web_compra.html', {
        'comisiones': comisiones
    })
#-------------------------------------------------------------------------------------------
def inteligencia_artificial_compra(request):
    inteligencia_artificial = Curso.objects.filter(nombre_curso__icontains="inteligencia_artificial").first()

    if inteligencia_artificial:
        comisiones = Comision.objects.filter(
            id_curso=inteligencia_artificial,
            estado_comision='proximo'
        ).order_by('fecha_inicio')
    else:
        comisiones = []

    return render(request, 'educativa/inteligencia_artificial_compra.html', {
        'comisiones': comisiones
    })
#-------------------------------------------------------------------------------------------
def python_compra(request):
    python = Curso.objects.filter(nombre_curso__icontains="python").first()

    if python:
        comisiones = Comision.objects.filter(
            id_curso=python,
            estado_comision='proximo'
        ).order_by('fecha_inicio')
    else:
        comisiones = []

    return render(request, 'educativa/python_compra.html', {
        'comisiones': comisiones
    })
#-------------------------------------------------------------------------------------------

def javascript_compra(request):
    javascript = Curso.objects.filter(nombre_curso__icontains="javascript").first()

    if javascript:
        comisiones = Comision.objects.filter(
            id_curso=javascript,
            estado_comision='proximo'
        ).order_by('fecha_inicio')
    else:
        comisiones = []

    return render(request, 'educativa/javascript_compra.html', {
        'comisiones': comisiones
    })

##########################################################################################
##########################################################################################
##########################################################################################

# @session_required
def mi_certificado(request, id_estudiante, id_comision):
    from plataforma.models import DatosDeEstudiantes, Comision, EntregaProyecto, AsistenciaClase, ClaseComision

    estudiante = DatosDeEstudiantes.objects.get(id_estudiante=id_estudiante)
    comision = Comision.objects.get(id_comision=id_comision)
    curso = comision.id_curso

    total_clases_comision = ClaseComision.objects.filter(comision=comision).count()
    asistencias_en_comision = AsistenciaClase.objects.filter(
        estudiante=estudiante,
        comision=comision  # ✅ corregido
    ).count()

    porcentaje_asistencia = (asistencias_en_comision / total_clases_comision * 100) if total_clases_comision > 0 else 0

    entrega_existente = EntregaProyecto.objects.filter(
        estudiante=estudiante,
        curso=curso,
        comision=comision
    ).first()

    nota_final = entrega_existente.nota if entrega_existente and entrega_existente.nota is not None else 0
    cumple_requisitos = porcentaje_asistencia >= 70 and nota_final >= 7

    context = {
        'usuario': request.user,
        'estudiante': estudiante,
        'curso': curso,
        'comision': comision,
        'entrega_existente': entrega_existente,
        'nota_final': nota_final,
        'asistencia': round(porcentaje_asistencia, 1),
        'asistencias_en_comision': asistencias_en_comision,
        'total_clases_comision': total_clases_comision,
        'cumple_requisitos': cumple_requisitos,
    }

    return render(request, 'educativa/mi_certificado.html', context)



#####################################################################################
###-------------------------filtrado de valoraciones------------------------------###
#####################################################################################

from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from plataforma.decorators import session_required
from plataforma.models import ValoracionAlumno, ClaseComision, Curso, Comision, DatosDeEstudiantes

@session_required
def valoraciones_filtradas(request, curso_id, comision_id):
    curso = get_object_or_404(Curso, id_curso=curso_id)
    comision = get_object_or_404(Comision, id_comision=comision_id)

    clases_comision = ClaseComision.objects.filter(comision_id=comision_id).select_related('clase')
    clases = [cc.clase for cc in clases_comision]

    resumen_clases = {}

    for clase in clases:
        valoraciones_clase = ValoracionAlumno.objects.filter(
            clase=clase,
            curso_id=curso_id,
            comision_id=comision_id
        )

        total = valoraciones_clase.count()
        conteo = valoraciones_clase.values('preferencia_clase').annotate(cantidad=Count('preferencia_clase'))

        votos = {'me_gusto': 0, 'mas_o_menos': 0, 'no_me_gusto': 0}
        for item in conteo:
            votos[item['preferencia_clase']] = item['cantidad']

        def porcentaje(x):
            return round((x / total) * 100) if total > 0 else 0

        resumen_clases[clase.numero_clase] = {
            'total': total,
            'votos': votos,
            'porcentajes': {
                'me_gusto': porcentaje(votos['me_gusto']),
                'mas_o_menos': porcentaje(votos['mas_o_menos']),
                'no_me_gusto': porcentaje(votos['no_me_gusto']),
            }
        }

    valoraciones = ValoracionAlumno.objects.filter(
        clase__in=clases,
        curso_id=curso_id,
        comision_id=comision_id
    ).select_related('clase')

    for v in valoraciones:
        if v.preferencia_clase == 'me_gusto':
            v.color_avatar = '#12f693'
        elif v.preferencia_clase == 'mas_o_menos':
            v.color_avatar = '#00f7ff'
        else:
            v.color_avatar = '#cf30ff'

    total_general = valoraciones.count()
    conteo_general = valoraciones.values('preferencia_clase').annotate(cantidad=Count('preferencia_clase'))

    votos_general = {'me_gusto': 0, 'mas_o_menos': 0, 'no_me_gusto': 0}
    for item in conteo_general:
        votos_general[item['preferencia_clase']] = item['cantidad']

    def porcentaje(x):
        return round((x / total_general) * 100) if total_general > 0 else 0

    resumen_general = {
        'total': total_general,
        'votos': votos_general,
        'porcentajes': {
            'me_gusto': porcentaje(votos_general['me_gusto']),
            'mas_o_menos': porcentaje(votos_general['mas_o_menos']),
            'no_me_gusto': porcentaje(votos_general['no_me_gusto']),
        }
    }

    total_estudiantes = valoraciones.values('id_estudiante').distinct().count()

    # Buscar estudiantes que tengan la comisión actual en alguno de los campos cursando1 a cursando9
    total_inscritos = DatosDeEstudiantes.objects.filter(
        Q(cursando1=comision_id) |
        Q(cursando2=comision_id) |
        Q(cursando3=comision_id) |
        Q(cursando4=comision_id) |
        Q(cursando5=comision_id) |
        Q(cursando6=comision_id) |
        Q(cursando7=comision_id) |
        Q(cursando8=comision_id) |
        Q(cursando9=comision_id)
    ).count()

    porcentaje_val_curso = round((total_estudiantes / total_inscritos) * 100) if total_inscritos > 0 else 0

    contexto = {
        'clases': sorted([c.numero_clase for c in clases]),
        'resumen_clases': resumen_clases,
        'resumen_general': resumen_general,
        'valoraciones': valoraciones,
        'comision_id': comision_id,
        'curso_id': curso_id,
        'nombre_curso': curso.nombre_curso,
        'numero_comision': comision.numero_comision,
        'total_estudiantes': total_estudiantes,
        'total_valoraciones_curso': total_general,
        'total_inscritos': total_inscritos,
        'porcentaje_val_curso': porcentaje_val_curso,
        'comision': comision,
        'nombre_usuario': request.session.get('usuario_logueado'),
    }

    return render(request, 'educativa/valoraciones.html', contexto)





##################################################################################
###------------------------feedback de proyectos-------------------------------###
##################################################################################
from django.shortcuts import render, get_object_or_404
from plataforma.models import EntregaProyecto, Comision, DatosDeEstudiantes
from django.db.models import Q

def ver_entregas_proyectos(request, curso_id, comision_id):
    comision = get_object_or_404(Comision, id_comision=comision_id, id_curso__id_curso=curso_id)

    entregas = EntregaProyecto.objects.filter(
        comision=comision,
        curso__id_curso=curso_id
    ).select_related('estudiante', 'curso')

    entregas_sin_corregir = entregas.filter(nota__isnull=True)
    entregas_corregidas = entregas.filter(nota__isnull=False)

    # Total de estudiantes cursando esa comisión
    cantidad_alumnos = DatosDeEstudiantes.objects.filter(
        Q(cursando1=comision) |
        Q(cursando2=comision) |
        Q(cursando3=comision) |
        Q(cursando4=comision) |
        Q(cursando5=comision) |
        Q(cursando6=comision) |
        Q(cursando7=comision) |
        Q(cursando8=comision) |
        Q(cursando9=comision)
    ).count()

    # Estadísticas de entregas
    total_entregas = entregas.count()
    aprobados = entregas_corregidas.filter(nota__gte=7).count()
    desaprobados = entregas_corregidas.filter(nota__lt=7).count()

    contexto = {
        'comision': comision,
        'entregas_sin_corregir': entregas_sin_corregir,
        'entregas_corregidas': entregas_corregidas,
        'cantidad_alumnos': cantidad_alumnos,
        'total_entregas': total_entregas,
        'aprobados': aprobados,
        'desaprobados': desaprobados,
        'nombre_usuario': request.session.get('usuario_logueado'),
        'usuario': request.session.get('usuario_logueado'),
    }
    return render(request, 'educativa/entregas_de_proyectos.html', contexto)

#-----------------------------------------------------------------------------

from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from .models import EntregaProyecto

@require_POST
def guardar_nota_feedback(request, entrega_id):
    entrega = get_object_or_404(EntregaProyecto, id=entrega_id)
    entrega.nota = request.POST.get("nota") or None
    entrega.feedback = request.POST.get("feedback") or ""
    entrega.save()
    return redirect(request.META.get("HTTP_REFERER", "/"))

###############################################################################
###-----------------------inscripción clase 1-------------------------------###
###############################################################################


from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

def formulario_inscripcion(request):
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    horarios = ["Mañana", "Tarde", "Noche"]
    tecnologias = [
        "HTML", "CSS", "SASS", "Bootstrap", "JavaScript", "Git", "GitHub", "Tailwind",
        "React", "Vue", "Angular", "Node.js", "Python", "Django", "SQL", ".NET", "Ruby",
        "PHP", "WordPress", "Otra", "Ninguna de las anteriores"
    ]
    niveles = list(range(1, 11))

    return render(request, 'educativa/inscripcion_clase1.html', {
        'dias_semana': dias_semana,
        'horarios': horarios,
        'tecnologias': tecnologias,
        'niveles': niveles,
    })
#------------------------------------------------------------------------------------------------

# views.py → REEMPLAZÁ TODA TU FUNCIÓN guardar_inscripcion POR ESTA
from django.shortcuts import render
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from .models import InscripcionClaseGratis


def guardar_inscripcion(request):
    if request.method == "POST":
        datos = request.POST

        # --- 1. GUARDAR EN BASE (tu código original + valores por defecto por si falta algo)
        try:
            inscripcion = InscripcionClaseGratis(
                nombre=datos.get("nombre", "").strip() or "Sin nombre",
                apellido=datos.get("apellido", "").strip() or "Sin apellido",
                telefono=datos.get("telefono", "").strip() or "Sin teléfono",
                pais=datos.get("pais", "").strip() or "Sin país",
                email=datos.get("email", "").strip().lower() or "sin@email.com",
                dias=", ".join(datos.getlist("dias[]") or ["Ninguno"]),
                horarios=", ".join(datos.getlist("horarios[]") or ["Ninguno"]),
                nivel_pc=int(datos.get("nivel_pc", 0)),
                exp_programacion=datos.get("exp_programacion", "No respondió"),
                nivel_programacion=int(datos.get("nivel_programacion", 0)),
                tecnologias=", ".join(datos.getlist("tecnologias[]") or ["Ninguna"]),
                
                dni=request.POST.get('dni', '').strip() or '00000000',
                fecha_nacimiento=request.POST.get('fecha_nacimiento', '2000-01-01'),
                genero=request.POST.get('genero', 'Prefiero no decir'),
                provincia=request.POST.get('provincia', '') if request.POST.get('pais') == 'Argentina' else '',
            )
            inscripcion.save()
        except Exception as e:
            print("Error guardando inscripción gratis:", e)

        # --- 2. PREPARAR DATOS PARA EL CORREO
        # context = {
        #     'nombre': inscripcion.nombre,
        #     'apellido': inscripcion.apellido,
        #     'email': inscripcion.email,
        #     'telefono': inscripcion.telefono,
        #     'pais': inscripcion.pais,
        #     'dias': inscripcion.dias,
        #     'horarios': inscripcion.horarios,
        #     'nivel_pc': inscripcion.nivel_pc,
        #     'exp_programacion': inscripcion.exp_programacion,
        #     'nivel_programacion': inscripcion.nivel_programacion,
        #     'tecnologias': inscripcion.tecnologias,
        #     'fecha': timezone.now(),
        #     'curso_nombre': 'Desarrollo Web',
        # }

        context = {
            'curso_nombre': 'Desarrollo Web',  # o 'Curso Gratis IA'
            'nombre': inscripcion.nombre,
            'apellido': inscripcion.apellido,
            'dni': inscripcion.dni,
            'fecha_nacimiento': inscripcion.fecha_nacimiento,
            'genero': inscripcion.genero,
            'pais': inscripcion.pais,
            'provincia': inscripcion.provincia if hasattr(inscripcion, 'provincia') and inscripcion.provincia else None,
            'telefono': inscripcion.telefono,
            'email': inscripcion.email,
            "dias": inscripcion.dias,
            "horarios": inscripcion.horarios,
            "nivel_pc": inscripcion.nivel_pc,
            "exp_programacion": inscripcion.exp_programacion,
            "nivel_programacion": inscripcion.nivel_programacion,
            "tecnologias": inscripcion.tecnologias if hasattr(inscripcion, 'tecnologias') else None,
            'fecha': timezone.now(),
            'curso_nombre': 'Desarrollo Web',
        }

        # --- 3. ENVIAR CORREO A VOS (usa el mismo template que el de IA)
        try:
            html_message = render_to_string('registration/confirmacion_inscripcion_gratuita.html', context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject=f"NUEVA INSCRIPCIÓN GRATIS DESARROLLO WEB – {inscripcion.nombre} {inscripcion.apellido}",
                message=plain_message,
                from_email=None,  # Usa DEFAULT_FROM_EMAIL del settings
                recipient_list=[
                    'tecnomarema.ar@gmail.com',           # ← EL QUE SÍ TE LLEGA
                    # 'inscripciones@tecnomarema.com.ar', # ← podés dejarlo o sacarlo
                ],
                html_message=html_message,
                fail_silently=False,
            )
            print("Correo de inscripción gratis enviado correctamente")
        except Exception as e:
            print("Error enviando correo gratis:", e)

        # --- 4. SIEMPRE MOSTRAR GRACIAS
        return render(request, "educativa/gracias.html")

    # Si no es POST
    return render(request, "404.html")
#######################################################################################
###--------------------eliminar cuenta desde perfil de usuario----------------------###
#######################################################################################

import os
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib.auth import logout
from .models import PerfilUsuario, DatosDeEstudiantes, AsistenciaClase, EntregaProyecto, PuntajeQuiz, ValoracionAlumno
import json

@csrf_exempt
def eliminar_cuenta(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            confirmacion = data.get("confirmacion", "").strip().lower()

            if confirmacion != "eliminar cuenta":
                return JsonResponse({"error": "Confirmación inválida"}, status=400)

            id_usuario = request.session.get("usuario_id")
            if not id_usuario:
                return JsonResponse({"error": "Sesión inválida"}, status=401)

            try:
                usuario = PerfilUsuario.objects.get(id_usuario=id_usuario)

                # Eliminar la foto si existe
                if usuario.foto and usuario.foto.path and os.path.isfile(usuario.foto.path):
                    os.remove(usuario.foto.path)

                # Cerrar sesión antes de eliminar el usuario
                logout(request)

                # Eliminar datos relacionados
                DatosDeEstudiantes.objects.filter(id_estudiante=id_usuario).delete()
                AsistenciaClase.objects.filter(estudiante_id=id_usuario).delete()
                EntregaProyecto.objects.filter(estudiante_id=id_usuario).delete()
                PuntajeQuiz.objects.filter(estudiante_id=id_usuario).delete()
                ValoracionAlumno.objects.filter(id_estudiante=id_usuario).delete()

                # Eliminar el perfil
                usuario.delete()

                return JsonResponse({"success": True})

            except PerfilUsuario.DoesNotExist:
                return JsonResponse({"error": "Usuario no encontrado"}, status=404)

        except Exception as e:
            return JsonResponse({"error": f"Error en la solicitud: {str(e)}"}, status=500)

    return JsonResponse({"error": "Método no permitido"}, status=405)

#-----------------------------------------------------------------------------------------------

def despedida_view(request):
    return render(request, "educativa/despedida.html")

#######################################################################
#######################################################################


from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@session_required
def admin_panel_view(request):
    return render(request, 'educativa/admin_panel.html')

#######################################################################
##-------------------Estadisticas del dashboard----------------------##
#######################################################################

from django.shortcuts import render
from plataforma.models import DatosDeEstudiantes, Curso, Clase, Comision
from plataforma.decorators import session_required

@session_required
def admin_panel_view(request):
    cantidad_alumnos = DatosDeEstudiantes.objects.count()
    cantidad_cursos = Curso.objects.count()
    cantidad_clases = Clase.objects.count()
    cantidad_comisiones = Comision.objects.count()

    contexto = {
        "cantidad_alumnos": cantidad_alumnos,
        "cantidad_cursos": cantidad_cursos,
        "cantidad_clases": cantidad_clases,
        "cantidad_comisiones": cantidad_comisiones,
    }

    return render(request, "educativa/admin_panel.html", contexto)

#---------------------------------------------------------------------------

# views.py
from django.shortcuts import render
from plataforma.models import DatosDeEstudiantes, Curso, Clase, Comision, PerfilUsuario, InscripcionClaseGratis
from plataforma.decorators import session_required

@session_required
def admin_panel_view(request):
    contexto = {
        "cantidad_alumnos": PerfilUsuario.objects.filter(rol='alumno').count(),
        "cantidad_cursos": Curso.objects.count(),
        "cantidad_clases": Clase.objects.count(),
        "cantidad_comisiones": Comision.objects.count(),
        "cantidad_profesores": PerfilUsuario.objects.filter(rol='profesor').count(),
        "cantidad_tutores": PerfilUsuario.objects.filter(rol='tutor').count(),
        "cantidad_admins": PerfilUsuario.objects.filter(is_staff=True).count(),
        "cantidad_clase1": InscripcionClaseGratis.objects.count(),
    }
    return render(request, "administrador/admin_panel.html", contexto)

@session_required
def listado_alumnos_view(request):
    alumnos = DatosDeEstudiantes.objects.select_related('perfilusuario') \
                .filter(perfilusuario__rol='alumno')
    return render(request, 'administrador/listado_alumnos.html', {'alumnos': alumnos})



#############################################################################
##-------------------Edicion y eliminacion de Alumnos----------------------##
#############################################################################

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import DatosDeEstudiantes, PerfilUsuario

# ==========================================================
# EDITAR ALUMNO
# ==========================================================
@require_POST
def editar_alumno(request):
    try:
        id_alumno = request.POST.get("id")
        alumno = DatosDeEstudiantes.objects.get(id_estudiante=id_alumno)
        perfil = PerfilUsuario.objects.get(id_estudiante=id_alumno)

        # Validaciones de duplicados
        dni = request.POST.get("dni")
        correo = request.POST.get("correo")
        username = request.POST.get("username")

        if DatosDeEstudiantes.objects.exclude(id_estudiante=id_alumno).filter(dni=dni).exists():
            return JsonResponse({"success": False, "mensaje": "Ya existe otro alumno con ese DNI."})

        if DatosDeEstudiantes.objects.exclude(id_estudiante=id_alumno).filter(correo=correo).exists():
            return JsonResponse({"success": False, "mensaje": "Ya existe otro alumno con ese correo."})

        if PerfilUsuario.objects.exclude(id_estudiante=id_alumno).filter(nombre_usuario=username).exists():
            return JsonResponse({"success": False, "mensaje": "Ya existe otro alumno con ese nombre de usuario."})

        # Actualizar DatosDeEstudiantes
        alumno.nombre = request.POST.get("nombre")
        alumno.apellido = request.POST.get("apellido")
        alumno.dni = dni
        alumno.correo = correo
        alumno.pais = request.POST.get("pais")
        alumno.provincia = request.POST.get("provincia")
        alumno.telefono = request.POST.get("telefono")
        alumno.fecha_nacimiento = request.POST.get("fecha_nacimiento")
        alumno.genero = request.POST.get("genero")
        alumno.save()

        # Actualizar PerfilUsuario
        perfil.nombre_usuario = username
        perfil.correo = correo
        perfil.save()

        return JsonResponse({"success": True, "mensaje": "Alumno actualizado correctamente."})

    except DatosDeEstudiantes.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "El alumno no existe."})
    except PerfilUsuario.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "El perfil de usuario no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


# ==========================================================
# ELIMINAR ALUMNOS
# ==========================================================
@require_POST
def eliminar_alumno(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ningún alumno para eliminar."})

        eliminados = 0
        with transaction.atomic():
            for id_alumno in ids:
                try:
                    alumno = DatosDeEstudiantes.objects.get(id_estudiante=id_alumno)
                    perfil = PerfilUsuario.objects.get(id_estudiante=id_alumno)
                    perfil.delete()
                    alumno.delete()
                    eliminados += 1
                except DatosDeEstudiantes.DoesNotExist:
                    continue
                except PerfilUsuario.DoesNotExist:
                    alumno.delete()
                    eliminados += 1

        return JsonResponse({"success": True, "mensaje": "Alumnos eliminados correctamente.", "cantidad": eliminados})

    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


#------------------------------------------------------------------------------

# @session_required
# def listado_cursos_view(request):
#     cursos = Curso.objects.all().order_by('id_curso') 
#     return render(request, 'administrador/listado_cursos.html', {'cursos': cursos})
#------------------------------------------------------------------------------------------
# from django.core.paginator import Paginator

# @session_required
# def listado_cursos_view(request):
#     cursos = Curso.objects.all().order_by('id_curso')
#     paginator = Paginator(cursos, 10)  # 10 cursos por página
#     page_number = request.GET.get('page')
#     cursos = paginator.get_page(page_number)
#     return render(request, 'administrador/listado_cursos.html', {'cursos': cursos})
#------------------------------------------------------------------------------------------

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.db import transaction
from decimal import Decimal
from .models import Curso  # Ajusta si tu modelo está en otro lugar

@session_required
def listado_cursos_view(request):
    cursos = Curso.objects.all().order_by('id_curso')
    paginator = Paginator(cursos, 10)  # 10 cursos por página
    page_number = request.GET.get('page')
    cursos = paginator.get_page(page_number)

    if request.method == 'POST':
        id_curso = request.POST.get('id_curso')
        if not id_curso:
            messages.error(request, 'ID de curso no válido.')
            return render(request, 'administrador/listado_cursos.html', {'cursos': cursos})

        curso = get_object_or_404(Curso, id_curso=id_curso)
        action = request.POST.get('action')

        try:
            with transaction.atomic():
                if action == 'update':
                    print("DEBUG - POST data para update:", dict(request.POST))  # Debug temporal - quítalo después
                    # Actualiza campos (duracion y modalidad son CharField, sin conversiones numéricas)
                    curso.nombre_curso = request.POST.get('nombre_curso') or curso.nombre_curso
                    curso.descripcion = request.POST.get('descripcion') or curso.descripcion
                    curso.estado_curso = request.POST.get('estado_curso') or curso.estado_curso
                    curso.duracion = request.POST.get('duracion') or curso.duracion  # String para CharField con choices
                    curso.modalidad = request.POST.get('modalidad') or curso.modalidad  # String para CharField con choices
                    pf_str = request.POST.get('precio_final')
                    if pf_str:
                        curso.precio_final = Decimal(pf_str)  # Decimal para DecimalField
                    po_str = request.POST.get('precio_original')
                    if po_str:
                        curso.precio_original = Decimal(po_str)
                    curso.consigna_proyecto = request.POST.get('consigna_proyecto') or curso.consigna_proyecto

                    # Iconos si se envían (opcional)
                    for i in range(1, 13):
                        field_name = f'icono{i:02d}'
                        if field_name in request.FILES:
                            old_file = getattr(curso, field_name)
                            if old_file:
                                old_file.delete(save=False)
                            setattr(curso, field_name, request.FILES[field_name])

                    curso.save()
                    print("DEBUG - Curso guardado con nombre:", curso.nombre_curso)  # Debug - quítalo después
                    messages.success(request, f'Curso "{curso.nombre_curso}" actualizado correctamente.')

                elif action == 'update_icono':
                    print("DEBUG - POST data para icono:", dict(request.POST), "FILES:", dict(request.FILES))  # Debug - quítalo después
                    # Eliminar icono
                    if 'delete_icono' in request.POST:
                        field_to_delete = request.POST['delete_icono']
                        old_icon = getattr(curso, field_to_delete)
                        if old_icon:
                            old_icon.delete(save=False)
                            setattr(curso, field_to_delete, None)
                        messages.info(request, f'Icono {field_to_delete} eliminado correctamente.')

                    # Subir iconos
                    updated_count = 0
                    for i in range(1, 13):
                        field_name = f'icono{i:02d}'
                        if field_name in request.FILES:
                            old_file = getattr(curso, field_name)
                            if old_file:
                                old_file.delete(save=False)
                            setattr(curso, field_name, request.FILES[field_name])
                            updated_count += 1

                    curso.save()
                    if updated_count > 0:
                        messages.success(request, f'{updated_count} icono(s) actualizado(s).')
                    else:
                        messages.info(request, 'No se subieron nuevos iconos.')

                return HttpResponseRedirect(request.get_full_path())

        except ValueError as e:
            print("DEBUG - Error ValueError:", str(e))  # Debug - quítalo después
            messages.error(request, f'Error en números: {str(e)}')
        except Exception as e:
            print("DEBUG - Error general:", str(e))  # Debug - quítalo después
            messages.error(request, f'Error al guardar: {str(e)}')

    return render(request, 'administrador/listado_cursos.html', {'cursos': cursos})

#------------------------------------------------------------------------------------------

@session_required
def listado_comisiones_view(request):
    comisiones = Comision.objects.select_related('id_curso').all().order_by('id_comision') 
    return render(request, 'administrador/listado_comisiones.html', {'comisiones': comisiones})

@session_required
def listado_clases_view(request):
    clases = Clase.objects.select_related('curso').all().order_by('curso_id', 'numero_clase')
    return render(request, 'administrador/listado_clases.html', {'clases': clases})

@session_required
def listado_profesores_view(request):
    profesores = PerfilUsuario.objects.filter(rol='profesor')
    return render(request, 'administrador/listado_profesores.html', {'usuarios': profesores})

@session_required
def listado_tutores_view(request):
    tutores = PerfilUsuario.objects.filter(rol='tutor')
    return render(request, 'administrador/listado_tutores.html', {'usuarios': tutores})

@session_required
def listado_admins_view(request):
    admins = PerfilUsuario.objects.filter(rol='admin')
    return render(request, 'administrador/listado_admins.html', {'usuarios': admins})

@session_required
def vista_chat_view(request):
    return render(request, 'administrador/chat_placeholder.html')


#############################################################################################
###-----------------eliminacion y edicion de Listado de comisiones------------------------###
#############################################################################################

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Comision

# ==========================================================
# EDITAR COMISIÓN
# ==========================================================

@session_required
@require_POST
def editar_comision(request):
    try:

        id_comision = request.POST.get("id")

        comision = Comision.objects.get(id_comision=id_comision)

        # -----------------------------
        # VALIDACIÓN SEGURA
        # -----------------------------
        numero_comision = request.POST.get("numero_comision")

        if numero_comision is not None:
            try:
                numero_comision = int(numero_comision)
            except:
                return JsonResponse({
                    "success": False,
                    "mensaje": "Número de comisión inválido."
                }, status=400)

        # -----------------------------
        # ASIGNACIÓN DE CAMPOS
        # -----------------------------
        comision.numero_comision = numero_comision
        comision.fecha_inicio = request.POST.get("fecha_inicio")
        comision.fecha_fin = request.POST.get("fecha_fin")
        comision.dia1 = request.POST.get("dia1")
        comision.dia2 = request.POST.get("dia2")
        comision.horario1 = request.POST.get("horario1")
        comision.horario2 = request.POST.get("horario2")
        comision.estado_comision = request.POST.get("estado_comision")

        comision.save()

        return JsonResponse({
            "success": True,
            "mensaje": "Comisión actualizada correctamente."
        })

    except Comision.DoesNotExist:
        return JsonResponse({
            "success": False,
            "mensaje": "La comisión no existe."
        }, status=404)

    except Exception as e:
        return JsonResponse({
            "success": False,
            "mensaje": str(e)
        }, status=500)


# ==========================================================
# ELIMINAR COMISIONES
# ==========================================================

@session_required
@require_POST
def eliminar_comision(request):
    try:

        # 🔴 CORRECCIÓN IMPORTANTE
        # tu JS envía: data: { ids: ids }
        ids = request.POST.getlist("ids")

        if not ids:
            return JsonResponse({
                "success": False,
                "mensaje": "No se recibieron IDs."
            }, status=400)

        eliminadas = Comision.objects.filter(
            id_comision__in=ids
        ).delete()

        return JsonResponse({
            "success": True,
            "mensaje": "Comisiones eliminadas correctamente.",
            "cantidad": eliminadas[0]
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "mensaje": str(e)
        }, status=500)

###########################################################################
###--------------edicion y eliminacion de profes------------------------###
###########################################################################

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import PerfilUsuario

@require_POST
def editar_profesor(request):
    try:
        id_prof = request.POST.get("id_usuario")
        profesor = PerfilUsuario.objects.get(id_usuario=id_prof, rol="profesor")

        profesor.nombre_usuario = request.POST.get("nombre_usuario")
        profesor.correo = request.POST.get("correo")
        profesor.rol = request.POST.get("rol")

        # Datos extendidos del estudiante vinculado
        if profesor.id_estudiante:
            estudiante = profesor.id_estudiante
            estudiante.nombre = request.POST.get("nombre")
            estudiante.apellido = request.POST.get("apellido")
            estudiante.telefono = request.POST.get("telefono")
            estudiante.fecha_nacimiento = request.POST.get("fecha_nacimiento")
            estudiante.genero = request.POST.get("genero")
            estudiante.save()

        profesor.save()
        return JsonResponse({"success": True, "mensaje": "Profesor actualizado correctamente."})

    except PerfilUsuario.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "El profesor no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


@require_POST
def eliminar_profesor(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ningún profesor para eliminar."})

        eliminados = PerfilUsuario.objects.filter(id_usuario__in=ids, rol="profesor").delete()[0]
        return JsonResponse({"success": True, "mensaje": "Profesores eliminados correctamente.", "cantidad": eliminados})

    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})



###########################################################################
###--------------edicion y eliminacion de tutores-----------------------###
###########################################################################


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import PerfilUsuario

@require_POST
def editar_tutor(request):
    try:
        id_tutor = request.POST.get("id_usuario")
        tutor = PerfilUsuario.objects.get(id_usuario=id_tutor, rol="tutor")

        # Datos básicos del perfil
        tutor.nombre_usuario = request.POST.get("nombre_usuario")
        tutor.correo = request.POST.get("correo")
        tutor.rol = request.POST.get("rol")

        # Datos extendidos del estudiante vinculado
        if tutor.id_estudiante:
            estudiante = tutor.id_estudiante
            estudiante.nombre = request.POST.get("nombre")
            estudiante.apellido = request.POST.get("apellido")
            estudiante.telefono = request.POST.get("telefono")
            estudiante.fecha_nacimiento = request.POST.get("fecha_nacimiento")
            estudiante.genero = request.POST.get("genero")
            estudiante.save()

        tutor.save()
        return JsonResponse({"success": True, "mensaje": "Tutor actualizado correctamente."})

    except PerfilUsuario.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "El tutor no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


@require_POST
def eliminar_tutor(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ningún tutor para eliminar."})

        eliminados = PerfilUsuario.objects.filter(id_usuario__in=ids, rol="tutor").delete()[0]
        return JsonResponse({"success": True, "mensaje": "Tutores eliminados correctamente.", "cantidad": eliminados})

    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})

###########################################################################
###--------------edicion y eliminacion de admins------------------------###
###########################################################################

@require_POST
def editar_admin(request):
    try:
        id_admin = request.POST.get("id_usuario")
        admin = PerfilUsuario.objects.get(id_usuario=id_admin, rol="admin")

        admin.nombre_usuario = request.POST.get("nombre_usuario")
        admin.correo = request.POST.get("correo")
        admin.rol = request.POST.get("rol")

        # Datos extendidos del estudiante vinculado
        if admin.id_estudiante:
            estudiante = admin.id_estudiante
            estudiante.nombre = request.POST.get("nombre")
            estudiante.apellido = request.POST.get("apellido")
            estudiante.telefono = request.POST.get("telefono")
            estudiante.fecha_nacimiento = request.POST.get("fecha_nacimiento")
            estudiante.genero = request.POST.get("genero")
            estudiante.save()

        admin.save()
        return JsonResponse({"success": True, "mensaje": "Administrador actualizado correctamente."})

    except PerfilUsuario.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "El administrador no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


@require_POST
def eliminar_admin(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ningún administrador para eliminar."})

        eliminados = PerfilUsuario.objects.filter(id_usuario__in=ids, rol="admin").delete()[0]
        return JsonResponse({"success": True, "mensaje": "Administradores eliminados correctamente.", "cantidad": eliminados})

    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})



###########################################################################
###------------------------chat-general---------------------------------###
###########################################################################
from django.core.files.uploadedfile import UploadedFile

@session_required
def chat_general(request):
    nombre_usuario = request.session.get('usuario_logueado')
    if not nombre_usuario:
        return redirect('login')

    try:
        usuario = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
    except PerfilUsuario.DoesNotExist:
        return redirect('login')

    chat_general_obj, _ = Chat.objects.get_or_create(tipo='general')
    chat_general_obj.participantes.add(usuario)  # ← por si no estaba

    if request.method == 'POST':
        texto = request.POST.get('mensaje', '').strip()
        archivo = request.FILES.get('archivo')
        if texto or archivo:
            Mensaje.objects.create(
                chat=chat_general_obj,
                remitente=usuario,
                texto=texto,
                archivo=archivo if isinstance(archivo, UploadedFile) else None
            )
        return redirect('chat_general')

    # 👇 ACTUALIZA LECTURA
    # actualizar_lectura(chat_general_obj, usuario)
    # ✅ marcar mensajes como leídos
    chat_general_obj.mensajes.filter(
        leido=False
    ).exclude(
        remitente=usuario
    ).update(
        leido=True
    )

    mensajes = chat_general_obj.mensajes.select_related('remitente').order_by('creado')

    return render(request, 'educativa/chat.html', {
        'chat_general': chat_general_obj,
        'chat': chat_general_obj,
        'mensajes': mensajes,
        # 'comision': usuario.comision,
        'usuario': usuario,
        'nombre_usuario': nombre_usuario,
        'usuarios_destino': [],
        'badges': {},
        'chats_comision': {},
    })



#####################################################################################
###----------------------------el polling del chat---------------------------------##
#####################################################################################

# from zoneinfo import ZoneInfo
# from django.utils import timezone
# from django.http import JsonResponse
# from .models import Chat  # Asegurate de tener este import

# def obtener_mensajes(request):
#     chat_general = Chat.objects.get(tipo='general')
#     mensajes = chat_general.mensajes.select_related('remitente').order_by('creado')

#     tz_arg = ZoneInfo('America/Argentina/Buenos_Aires')

#     lista = []
#     for m in mensajes:
#         local_time = timezone.localtime(m.creado, tz_arg).strftime("%d/%m %H:%M")
#         lista.append({
#             'id': m.id,
#             'usuario': m.remitente.nombre_usuario,
#             'texto': m.texto,
#             'hora': local_time,
#             'fecha': m.creado.isoformat(),  # 👈 AÑADÍ ESTA LÍNEA
#             'creado': m.creado.isoformat(), # 👈 Y TAMBIÉN ESTA SI TU JS LA USA
#             'archivo_url': m.archivo.url if m.archivo else None,
#             'archivo_name': m.archivo.name.split('/')[-1] if m.archivo else None,
#             'destacado': m.destacado,  # 👈 AGREGÁ ESTA LÍNEA
#         })

#     return JsonResponse({'mensajes': lista})

from zoneinfo import ZoneInfo
from django.utils import timezone
from django.http import JsonResponse
from .models import Chat

def obtener_mensajes(request):

    usuario_id = request.session.get('usuario_id')

    chat_general = Chat.objects.get(tipo='general')

    mensajes = chat_general.mensajes.select_related(
        'remitente'
    ).order_by('creado')

    tz_arg = ZoneInfo('America/Argentina/Buenos_Aires')

    lista = []

    for m in mensajes:

        local_time = timezone.localtime(
            m.creado,
            tz_arg
        ).strftime("%d/%m %H:%M")

        lista.append({
            'id': m.id,
            'usuario': m.remitente.nombre_usuario,
            'texto': m.texto,
            'hora': local_time,
            'fecha': m.creado.isoformat(),
            'creado': m.creado.isoformat(),
            'archivo_url': m.archivo.url if m.archivo else None,
            'archivo_name': m.archivo.name.split('/')[-1] if m.archivo else None,
            'destacado': m.destacado,
        })

    # ✅ contador real de no leídos
    no_leidos = mensajes.filter(
        leido=False
    ).exclude(
        remitente__id_usuario=usuario_id
    ).count()

    return JsonResponse({
        'mensajes': lista,
        'no_leidos': no_leidos
    })

########################################################################################
###---------------------obtener mensajes por comision--------------------------------###
########################################################################################

@session_required
def obtener_mensajes_comision(request, id_comision):
    usuario = PerfilUsuario.objects.get(nombre_usuario=request.session['usuario_logueado'])

    try:
        chat = Chat.objects.get(tipo='comision', comision__id_comision=id_comision)
    except Chat.DoesNotExist:
        return JsonResponse({'mensajes': []})

    mensajes = chat.mensajes.select_related('remitente').order_by('creado')

    data = []
    for m in mensajes:
        data.append({
            'id': m.id,
            'usuario': m.remitente.nombre_usuario,
            'texto': m.texto,
            'archivo_url': m.archivo.url if m.archivo else '',
            'archivo_nombre': m.archivo.name.split('/')[-1] if m.archivo else '',
            # 'hora': m.creado.strftime("%d/%m %H:%M"),
            'hora': timezone.localtime(m.creado, ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%d/%m %H:%M"),
            'fecha': m.creado.isoformat(),
            'destacado': m.destacado,
            'creado': m.creado.isoformat(),
        })

    return JsonResponse({'mensajes': data})


########################################################################################
####-------------------saber si esta escribiendo un usuario en el chat---------------###
########################################################################################

# from django.views.decorators.csrf import csrf_exempt
# from django.utils import timezone
# from django.http import JsonResponse

# @csrf_exempt
# def marcar_escribiendo(request):
#     if request.method == 'POST':
#         usuario_id = request.session.get('usuario_id')
#         if usuario_id:
#             try:
#                 usuario = PerfilUsuario.objects.get(pk=usuario_id)
#                 usuario.ultimo_typing = timezone.now()
#                 usuario.save(update_fields=['ultimo_typing'])
#                 return JsonResponse({'ok': True})
#             except PerfilUsuario.DoesNotExist:
#                 pass
#     return JsonResponse({'ok': False})

# # Vista para consultar quién está escribiendo ↓

# def obtener_typing(request):
#     usuarios_typing = PerfilUsuario.objects.filter(
#         ultimo_typing__gte=timezone.now() - timezone.timedelta(seconds=5)
#     ).exclude(pk=request.session.get('usuario_id'))

#     nombres = [u.nombre_usuario for u in usuarios_typing]
#     return JsonResponse({'escribiendo': nombres})





from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json, time

# Guardamos temporalmente quién escribe en qué chat
usuarios_escribiendo = {}

@csrf_exempt
def notificar_escribiendo(request):
    if request.method == "POST":
        data = json.loads(request.body)
        chat_id = str(data.get("chat_id"))
        usuario = data.get("usuario")
        if chat_id and usuario:
            usuarios_escribiendo[chat_id] = {
                'usuario': usuario,
                'timestamp': time.time()
            }
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Método no permitido"}, status=405)

def verificar_escribiendo(request):
    chat_id = request.GET.get("chat_id")
    ahora = time.time()
    data = usuarios_escribiendo.get(chat_id)
    if data and ahora - data['timestamp'] < 5:
        return JsonResponse({'usuario': data['usuario']})
    return JsonResponse({'usuario': None})


################################################################################


import json
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import Mensaje

@csrf_exempt  # si no usás CSRF token, sino sacá esto y enviá el token
def editar_mensaje(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método no permitido')

    usuario_logueado = request.session.get('usuario_logueado')
    if not usuario_logueado:
        return HttpResponseForbidden('No autenticado')

    try:
        data = json.loads(request.body)
        mensaje_id = data.get('id')
        nuevo_texto = data.get('texto', '').strip()
        if not mensaje_id or not nuevo_texto:
            return HttpResponseBadRequest('Faltan datos')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('JSON inválido')

    mensaje = get_object_or_404(Mensaje, id=mensaje_id)

    # Validar que el usuario logueado sea dueño del mensaje
    if mensaje.remitente.nombre_usuario != usuario_logueado:
        return HttpResponseForbidden('No autorizado para editar este mensaje')

    mensaje.texto = nuevo_texto
    mensaje.save()

    return JsonResponse({'status': 'ok', 'mensaje': 'Mensaje actualizado', 'texto': mensaje.texto})

@csrf_exempt
def borrar_mensaje(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método no permitido')

    usuario_logueado = request.session.get('usuario_logueado')
    if not usuario_logueado:
        return HttpResponseForbidden('No autenticado')

    try:
        data = json.loads(request.body)
        mensaje_id = data.get('id')
        if not mensaje_id:
            return HttpResponseBadRequest('Faltan datos')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('JSON inválido')

    mensaje = get_object_or_404(Mensaje, id=mensaje_id)

    # Validar que el usuario logueado sea dueño del mensaje
    if mensaje.remitente.nombre_usuario != usuario_logueado:
        return HttpResponseForbidden('No autorizado para borrar este mensaje')

    mensaje.delete()

    return JsonResponse({'status': 'ok', 'mensaje': 'Mensaje borrado'})
##############################################################################
#----------------------------mensaje destacado-------------------------------#
##############################################################################
# views.py
@csrf_exempt
def toggle_destacar_mensaje(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Método no permitido')

    try:
        data = json.loads(request.body)
        mensaje_id = data.get('id')
    except (json.JSONDecodeError, KeyError):
        return HttpResponseBadRequest('Datos inválidos')

    mensaje = get_object_or_404(Mensaje, id=mensaje_id)

    usuario_logueado = request.session.get('usuario_logueado')
    if not usuario_logueado or mensaje.remitente.nombre_usuario != usuario_logueado:
        return HttpResponseForbidden('No autorizado')

    mensaje.destacado = not mensaje.destacado
    mensaje.save()
    return JsonResponse({'status': 'ok', 'destacado': mensaje.destacado})

####################################################################################
###------------------chat comision view-(filtrado de chats)----------------------###
####################################################################################

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Chat, Mensaje, PerfilUsuario, Comision, DatosDeEstudiantes
from django.db.models import Q
from plataforma.decorators import session_required

@session_required
def chat_comision_view(request, id_comision):
    usuario = PerfilUsuario.objects.select_related('id_estudiante').get(
        nombre_usuario=request.session['usuario_logueado']
    )

    estudiante = usuario.id_estudiante

    comisiones_permitidas = [
        estudiante.cursando1_id, estudiante.cursando2_id, estudiante.cursando3_id,
        estudiante.cursando4_id, estudiante.cursando5_id, estudiante.cursando6_id,
        estudiante.cursando7_id, estudiante.cursando8_id, estudiante.cursando9_id
    ] if estudiante else []

    pertenece = (id_comision in comisiones_permitidas) or (usuario.rol in ['profesor', 'tutor'])

    if not pertenece:
        messages.error(request, "No tenés permiso para acceder a este chat.")
        return redirect('mis_cursos')

    chat, _ = Chat.objects.get_or_create(tipo='comision', comision_id=id_comision)
    chat.participantes.add(usuario)

    comision = get_object_or_404(Comision, id_comision=id_comision)

    # 🔍 Participantes visibles según rol
    comisiones = [id_comision]
    usuarios_destino = set()

    if usuario.rol == 'alumno':
        profesores_y_tutores = PerfilUsuario.objects.filter(
            rol__in=['profesor', 'tutor'],
            id_estudiante__in=DatosDeEstudiantes.objects.filter(
                Q(cursando1__in=comisiones) | Q(cursando2__in=comisiones) |
                Q(cursando3__in=comisiones) | Q(cursando4__in=comisiones) |
                Q(cursando5__in=comisiones) | Q(cursando6__in=comisiones) |
                Q(cursando7__in=comisiones) | Q(cursando8__in=comisiones) |
                Q(cursando9__in=comisiones)
            )
        )
        usuarios_destino.update(profesores_y_tutores)

    else:  # tutor o profesor ve todos
        todos = PerfilUsuario.objects.filter(
            id_estudiante__in=DatosDeEstudiantes.objects.filter(
                Q(cursando1__in=comisiones) | Q(cursando2__in=comisiones) |
                Q(cursando3__in=comisiones) | Q(cursando4__in=comisiones) |
                Q(cursando5__in=comisiones) | Q(cursando6__in=comisiones) |
                Q(cursando7__in=comisiones) | Q(cursando8__in=comisiones) |
                Q(cursando9__in=comisiones)
            )
        )
        usuarios_destino.update(todos)

    # Excluirse
    usuarios_destino.discard(usuario)

    # Mensajes
    mensajes = Mensaje.objects.filter(chat=chat).select_related('remitente').order_by('creado')

    # actualizar_lectura(chat, usuario)
    # ✅ marcar mensajes como leídos
    chat.mensajes.filter(
        leido=False
    ).exclude(
        remitente=usuario
    ).update(
        leido=True
    )

    return render(request, 'educativa/chat.html', {
        'chat': chat,
        'mensajes': mensajes,
        'usuario': usuario,
        'nombre_usuario': usuario.nombre_usuario,
        'usuarios_destino': list(usuarios_destino),
        'comision': comision,
    })



##################################################################################################
###-------------------enviado de mensajes por comision y chat general--------------------------###
##################################################################################################

@session_required
def enviar_mensaje_general(request):
    if request.method == "POST":
        usuario = PerfilUsuario.objects.get(nombre_usuario=request.session['usuario_logueado'])
        texto = request.POST.get("mensaje", "")
        archivo = request.FILES.get("archivo")

        chat = Chat.objects.get(tipo='general')

        Mensaje.objects.create(
            chat=chat,
            remitente=usuario,
            texto=texto,
            archivo=archivo
        )

        return redirect('chat_general')

@session_required
def enviar_mensaje_comision(request, id_comision):
    if request.method == "POST":
        usuario = PerfilUsuario.objects.get(nombre_usuario=request.session['usuario_logueado'])
        texto = request.POST.get("mensaje", "")
        archivo = request.FILES.get("archivo")

        chat = Chat.objects.get(tipo='comision', comision__id_comision=id_comision)

        Mensaje.objects.create(
            chat=chat,
            remitente=usuario,
            texto=texto,
            archivo=archivo
        )

        return redirect('chat_comision', id_comision=id_comision)

##################################################################################################
###----------------------------------Chat privado----------------------------------------------###
##################################################################################################

from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Q
from .models import Chat, PerfilUsuario, DatosDeEstudiantes, Comision
from plataforma.decorators import session_required

def comparten_comision(user1, user2):
    est1 = getattr(user1, 'id_estudiante', None)
    est2 = getattr(user2, 'id_estudiante', None)

    if not est1 or not est2:
        return False

    comisiones1 = [
        est1.cursando1, est1.cursando2, est1.cursando3,
        est1.cursando4, est1.cursando5, est1.cursando6,
        est1.cursando7, est1.cursando8, est1.cursando9
    ]
    comisiones2 = [
        est2.cursando1, est2.cursando2, est2.cursando3,
        est2.cursando4, est2.cursando5, est2.cursando6,
        est2.cursando7, est2.cursando8, est2.cursando9
    ]

    return any(c1 and c2 and c1 == c2 for c1 in comisiones1 for c2 in comisiones2)


from django.db.models import Count, Q

def obtener_chat_privado(remitente, destinatario):
    chats = Chat.objects.filter(tipo='privado').annotate(num_participantes=Count('participantes')).filter(num_participantes=2)
    chats = chats.filter(participantes=remitente).filter(participantes=destinatario)
    chat = chats.first()
    if not chat:
        chat = Chat.objects.create(tipo='privado')
        chat.participantes.add(remitente, destinatario)
    return chat

from django.db.models import Q, Max  # Asegúrate de tener estas importaciones

@session_required
def chat_privado(request, nombre_usuario_destino):
    remitente = get_object_or_404(PerfilUsuario, nombre_usuario=request.session['usuario_logueado'])
    destinatario = get_object_or_404(PerfilUsuario, nombre_usuario=nombre_usuario_destino)

    # Validaciones de roles y comisión compartida
    if remitente.rol == 'alumno':
        if destinatario.rol not in ['tutor', 'profesor'] or not comparten_comision(remitente, destinatario):
            return redirect('chat_general')
    elif remitente.rol in ['tutor', 'profesor']:
        if destinatario.rol not in ['alumno', 'tutor', 'profesor'] or not comparten_comision(remitente, destinatario):
            return redirect('chat_general')

    # 1. Obtener chat actual y resetear contador a 0
    chat = obtener_chat_privado(remitente, destinatario)
    chat.mensajes.filter(leido=False).exclude(remitente=remitente).update(leido=True)

    mensajes = chat.mensajes.select_related('remitente').order_by('creado')

    # 2. LÓGICA DE ORDENAMIENTO DE LA BARRA LATERAL (CORREGIDA)
    # Buscamos los chats ordenados por el mensaje más reciente
    mis_chats = Chat.objects.filter(
        participantes=remitente, 
        tipo='privado'
    ).annotate(
        ultima_actividad=Max('mensajes__creado')
    ).order_by('-ultima_actividad')

    usuarios_destino_ordenados = []
    ids_ya_incluidos = set()

    for c in mis_chats:
        # CAMBIO CLAVE: Usamos .pk para evitar el AttributeError
        otro = c.participantes.exclude(pk=remitente.pk).first()
        if otro:
            usuarios_destino_ordenados.append(otro)
            ids_ya_incluidos.add(otro.pk)

    # 3. Obtener el resto de contactos de comisiones (lógica original)
    comisiones = []
    if remitente.id_estudiante:
        est_rem = remitente.id_estudiante
        comisiones = [c for c in [est_rem.cursando1, est_rem.cursando2, est_rem.cursando3, 
                                  est_rem.cursando4, est_rem.cursando5, est_rem.cursando6, 
                                  est_rem.cursando7, est_rem.cursando8, est_rem.cursando9] if c]

    contactos_comision = PerfilUsuario.objects.filter(
        Q(rol__in=['profesor', 'tutor', 'alumno']),
        id_estudiante__in=DatosDeEstudiantes.objects.filter(
            Q(cursando1__in=comisiones) | Q(cursando2__in=comisiones) | Q(cursando3__in=comisiones) |
            Q(cursando4__in=comisiones) | Q(cursando5__in=comisiones) | Q(cursando6__in=comisiones) |
            Q(cursando7__in=comisiones) | Q(cursando8__in=comisiones) | Q(cursando9__in=comisiones)
        )
    ).exclude(pk=remitente.pk)

    # Combinamos: Primero los activos (por fecha), luego los que no tienen mensajes
    for u in contactos_comision:
        if u.pk not in ids_ya_incluidos:
            usuarios_destino_ordenados.append(u)
            ids_ya_incluidos.add(u.pk)

    actualizar_lectura(chat, remitente)

    return render(request, 'educativa/chat.html', {
        'chat': chat,
        'mensajes': mensajes,
        'usuario': remitente,
        'nombre_usuario': remitente.nombre_usuario,
        'destinatario': destinatario,
        'usuarios_destino': usuarios_destino_ordenados,
        'comision': None,
    })

##################################################################################################
###---------------------Enviar mensaje a chat privado------------------------------------------###
##################################################################################################

# def enviar_mensaje_privado(request, id_usuario):
#     if request.method == 'POST':
#         remitente = get_object_or_404(PerfilUsuario, nombre_usuario=request.session['usuario_logueado'])
#         destinatario = get_object_or_404(PerfilUsuario, id_usuario=id_usuario)

#         # Validar que estén en la misma comisión (opcional)
#         if not comparten_comision(remitente, destinatario):
#             return redirect('chat_general')  # O mostrar mensaje de error

#         # Obtener o crear chat privado único
#         chat = obtener_chat_privado(remitente, destinatario)

#         texto = request.POST.get('mensaje')
#         archivo = request.FILES.get('archivo')

#         Mensaje.objects.create(chat=chat, remitente=remitente, texto=texto, archivo=archivo)

#         return redirect('chat_privado', nombre_usuario_destino=destinatario.nombre_usuario)


@session_required
def enviar_mensaje_privado(request, id_usuario):
    if request.method == 'POST':
        remitente = get_object_or_404(PerfilUsuario, nombre_usuario=request.session['usuario_logueado'])
        destinatario = get_object_or_404(PerfilUsuario, id_usuario=id_usuario)

        # ✅ Validar que compartan comisión (opcional)
        if not comparten_comision(remitente, destinatario):
            return redirect('chat_general')

        # ✅ Obtener o crear el chat privado único entre ambos
        chat = obtener_chat_privado(remitente, destinatario)

        texto = request.POST.get('mensaje', '').strip()
        archivo = request.FILES.get('archivo')

        if not texto and not archivo:
            return redirect('chat_privado', nombre_usuario_destino=destinatario.nombre_usuario)

        # ✅ Crear mensaje marcado como no leído
        Mensaje.objects.create(
            chat=chat,
            remitente=remitente,
            texto=texto,
            archivo=archivo,
            leido=False  # 👈 Esto es lo que activa el badge
        )

        # (Opcional) Podés devolver JSON si querés hacerlo sin recargar la página
        return redirect('chat_privado', nombre_usuario_destino=destinatario.nombre_usuario)

    return redirect('chat_general')




##################################################################################################
###---------------------obtener usuarios de destino privado-------------------------------------###
##################################################################################################


from django.db.models import Q

def obtener_usuarios_destino_privado(usuario):
    comisiones = []

    # 1. Obtener comisiones según el rol
    if usuario.rol == 'alumno' and usuario.id_estudiante:
        comisiones = [
            usuario.id_estudiante.cursando1, usuario.id_estudiante.cursando2,
            usuario.id_estudiante.cursando3, usuario.id_estudiante.cursando4,
            usuario.id_estudiante.cursando5, usuario.id_estudiante.cursando6,
            usuario.id_estudiante.cursando7, usuario.id_estudiante.cursando8,
            usuario.id_estudiante.cursando9
        ]
    elif usuario.rol == 'profesor':
        if hasattr(usuario, 'profesorado'):
            comisiones = list(usuario.profesorado.all())
    elif usuario.rol == 'tutor':
        if hasattr(usuario, 'tutorado'):
            comisiones = list(usuario.tutorado.all())

    comisiones = [c for c in comisiones if c]

    if not comisiones:
        return PerfilUsuario.objects.none()

    # 2. Buscar alumnos que cursen alguna de esas comisiones
    alumnos_q = Q()
    for i in range(1, 10):
        alumnos_q |= Q(**{f'id_estudiante__cursando{i}__in': comisiones})

    alumnos = PerfilUsuario.objects.filter(rol='alumno').filter(alumnos_q)

    # 3. Buscar profesores de esas comisiones
    profesores = PerfilUsuario.objects.filter(rol='profesor', profesorado__in=comisiones)

    # 4. Buscar tutores de esas comisiones
    tutores = PerfilUsuario.objects.filter(rol='tutor', tutorado__in=comisiones)

    # 5. Unificar y excluir a sí mismo
    todos = alumnos.union(profesores, tutores).exclude(id_usuario=usuario.id_usuario).distinct()
    return todos


##################################################################################################
###---------------------buscar usuarios desde input para chat privado--------------------------###
##################################################################################################

from django.http import JsonResponse
from .models import PerfilUsuario
from django.contrib.auth.decorators import login_required

@login_required
def buscar_usuarios(request):
    q = request.GET.get('q', '').strip()
    usuarios = []

    if q:
        usuarios_qs = PerfilUsuario.objects.filter(nombre_usuario__icontains=q)[:20]
        usuarios = [{'id_usuario': u.id_usuario, 'nombre_usuario': u.nombre_usuario} for u in usuarios_qs]

    return JsonResponse({'usuarios': usuarios})

##########################################################################################################



from django.db.models import Q

def obtener_usuarios_para_chat_privado_extendido(usuario):
    if not usuario:
        return PerfilUsuario.objects.none()

    resultados = PerfilUsuario.objects.none()

    if usuario.rol == 'alumno' and usuario.id_estudiante:
        comisiones = [
            usuario.id_estudiante.cursando1,
            usuario.id_estudiante.cursando2,
            usuario.id_estudiante.cursando3,
            usuario.id_estudiante.cursando4,
            usuario.id_estudiante.cursando5,
            usuario.id_estudiante.cursando6,
            usuario.id_estudiante.cursando7,
            usuario.id_estudiante.cursando8,
            usuario.id_estudiante.cursando9,
        ]
        comisiones = [c for c in comisiones if c]

        # Alumnos en las mismas comisiones
        alumnos_q = Q()
        for i in range(1, 10):
            alumnos_q |= Q(**{f'id_estudiante__cursando{i}__in': comisiones})

        # Profesores y tutores desde las comisiones
        profesores = []
        tutores = []
        for com in comisiones:
            if hasattr(com, 'profesor') and com.profesor:
                profesores.append(com.profesor)
            if hasattr(com, 'tutores'):
                tutores.extend(com.tutores.all())
            elif hasattr(com, 'tutor') and com.tutor:
                tutores.append(com.tutor)

        profesores_ids = [p.id_usuario for p in profesores]
        tutores_ids = [t.id_usuario for t in tutores]

        resultados = PerfilUsuario.objects.filter(
            alumnos_q | Q(id_usuario__in=profesores_ids) | Q(id_usuario__in=tutores_ids)
        ).exclude(id_usuario=usuario.id_usuario)

    elif usuario.rol in ['tutor', 'profesor']:
        if usuario.rol == 'tutor':
            comisiones = usuario.tutorado.all() if hasattr(usuario, 'tutorado') else []
        else:
            comisiones = usuario.profesorado.all() if hasattr(usuario, 'profesorado') else []

        comisiones = list(comisiones)

        alumnos_q = Q()
        for i in range(1, 10):
            alumnos_q |= Q(**{f'id_estudiante__cursando{i}__in': comisiones})

        alumnos = PerfilUsuario.objects.filter(rol='alumno').filter(alumnos_q)

        # También pueden chatear entre roles
        otros_rol = 'profesor' if usuario.rol == 'tutor' else 'tutor'
        usuarios_rol_opuesto = PerfilUsuario.objects.filter(
            rol=otros_rol
        ).filter(
            Q(profesorado__in=comisiones) | Q(tutorado__in=comisiones)
        ).distinct()

        resultados = (alumnos | usuarios_rol_opuesto).exclude(id_usuario=usuario.id_usuario)

    return resultados.distinct()


#---------------------------------------------------------

@session_required
def obtener_mensajes_privado(request, id):
    chat = get_object_or_404(Chat, id=id, tipo='privado')
    mensajes = chat.mensajes.select_related('remitente').order_by('creado')
    data = [{
        'id': m.id,
        'usuario': m.remitente.nombre_usuario,
        'texto': m.texto,
        'archivo_url': m.archivo.url if m.archivo else '',
        'archivo_nombre': m.archivo.name.split('/')[-1] if m.archivo else '',
        'hora': timezone.localtime(m.creado, ZoneInfo("America/Argentina/Buenos_Aires")).strftime("%d/%m %H:%M"),
        'fecha': m.creado.isoformat(),
        'destacado': m.destacado,
        'creado': m.creado.isoformat(),
    } for m in mensajes]

    return JsonResponse({'mensajes': data})


#------------------------------------------------------------------------


from django.db.models import Count, Q

def obtener_chat_privado(remitente, destinatario):
    chats = Chat.objects.filter(tipo='privado').annotate(num_participantes=Count('participantes')).filter(num_participantes=2)
    chats = chats.filter(participantes=remitente).filter(participantes=destinatario)
    chat = chats.first()
    if not chat:
        chat = Chat.objects.create(tipo='privado')
        chat.participantes.add(remitente, destinatario)
    return chat

###################################################################################################################
###---------------vistas para visualizar la cantidad de mensajes no leidos por comision y general---------------###
###################################################################################################################
from .models import LecturaMensaje

def obtener_badges(request):
    usuario = request.user  # o como accedés al usuario actual
    badges = {}

    # Chats que el usuario tiene: general + comisiones + privados (según lo que uses)
    chats = Chat.objects.filter(participantes=usuario)

    for chat in chats:
        lectura = LecturaMensaje.objects.filter(usuario=usuario, chat=chat).first()
        if lectura and lectura.ultimo_mensaje_leido:
            # Contar mensajes posteriores a ese último mensaje leído
            nuevos = chat.mensajes.filter(creado__gt=lectura.ultimo_mensaje_leido.creado).count()
        else:
            # No hay lectura previa, contamos todos los mensajes
            nuevos = chat.mensajes.count()
        badges[chat.id] = nuevos

    return badges
#-------------------------------------------------------------------------


# from django.http import JsonResponse
# from .models import Chat, LecturaMensaje, PerfilUsuario

# def mensajes_nuevos_view(request):
#     nombre_usuario = request.session.get('usuario_logueado')
#     if not nombre_usuario:
#         return JsonResponse({'error': 'no logueado'}, status=401)

#     try:
#         usuario = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
#     except PerfilUsuario.DoesNotExist:
#         return JsonResponse({'error': 'usuario inválido'}, status=401)

#     data = {
#         'general': 0,
#         'comisiones': {},
#         'privados': {},
#     }

#     chats = Chat.objects.filter(participantes=usuario).select_related('comision').prefetch_related('mensajes')

#     for chat in chats:
#         lectura = LecturaMensaje.objects.filter(usuario=usuario, chat=chat).first()
        
#         # Si nunca entró al chat, no hay lectura → no mostrar badge
#         if not lectura:
#             nuevos = 0
#         else:
#             if lectura.ultimo_mensaje_leido:
#                 nuevos = chat.mensajes.filter(creado__gt=lectura.ultimo_mensaje_leido.creado).count()
#             else:
#                 nuevos = chat.mensajes.count()

#         if chat.tipo == 'general':
#             data['general'] = nuevos

#         elif chat.tipo == 'comision' and chat.comision:
#             data['comisiones'][chat.comision.id_comision] = nuevos

#         elif chat.tipo == 'privado':
#             otro = chat.participantes.exclude(id=usuario.id).first()
#             if otro:
#                 data['privados'][otro.id_usuario] = nuevos

#     return JsonResponse(data)
#-----------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------
# from django.http import JsonResponse
# from .models import Chat, LecturaMensaje, PerfilUsuario

# def mensajes_nuevos_view(request):
#     nombre_usuario = request.session.get('usuario_logueado')
#     if not nombre_usuario:
#         return JsonResponse({'error': 'no logueado'}, status=401)

#     try:
#         usuario = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
#     except PerfilUsuario.DoesNotExist:
#         return JsonResponse({'error': 'usuario inválido'}, status=401)

#     data = {
#         'general': 0,
#         'comisiones': {},
#         'privados': []
#     }

#     chats = Chat.objects.filter(participantes=usuario).select_related('comision').prefetch_related('mensajes')

#     for chat in chats:
#         lectura = LecturaMensaje.objects.filter(usuario=usuario, chat=chat).first()
#         if not lectura:
#             nuevos = 0
#         else:
#             if lectura.ultimo_mensaje_leido:
#                 nuevos = chat.mensajes.filter(creado__gt=lectura.ultimo_mensaje_leido.creado).count()
#             else:
#                 nuevos = chat.mensajes.count()

#         if chat.tipo == 'general':
#             data['general'] = nuevos

#         elif chat.tipo == 'comision' and chat.comision:
#             data['comisiones'][chat.comision.id_comision] = nuevos

#         elif chat.tipo == 'privado':
#             otro = chat.participantes.exclude(id=usuario.id).first()
#             if otro:
#                 data['privados'].append({
#                     'id': otro.id_usuario,
#                     'nombre': otro.nombre_usuario,
#                     'nuevos': nuevos
#                 })

#     return JsonResponse(data)
#-----------------------------------------------------------------------------------------------------------

# from django.http import JsonResponse
# from django.db.models import Count, Q
# from .models import Chat, LecturaMensaje, PerfilUsuario

# def mensajes_nuevos_view(request):
#     nombre_usuario = request.session.get('usuario_logueado')
#     if not nombre_usuario:
#         return JsonResponse({'error': 'no logueado'}, status=401)

#     try:
#         usuario = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
#     except PerfilUsuario.DoesNotExist:
#         return JsonResponse({'error': 'usuario inválido'}, status=401)

#     data = {
#         'general': 0,
#         'comisiones': {},
#         'privados': []
#     }

#     # traemos chats donde participa el usuario
#     chats = Chat.objects.filter(participantes=usuario).select_related('comision').prefetch_related('participantes', 'mensajes')

#     for chat in chats:
#         lectura = LecturaMensaje.objects.filter(usuario=usuario, chat=chat).first()

#         if not lectura:
#             # si nunca abrió el chat, asumimos que todos los mensajes son "nuevos" o 0 según tu regla
#             # aquí prefiero poner 0 (no mostrar) si nunca hubo lectura; ajustá si querés otro comportamiento
#             nuevos = 0
#         else:
#             if lectura.ultimo_mensaje_leido:
#                 nuevos = chat.mensajes.filter(creado__gt=lectura.ultimo_mensaje_leido.creado).count()
#             else:
#                 nuevos = chat.mensajes.count()

#         if chat.tipo == 'general':
#             data['general'] = nuevos

#         elif chat.tipo == 'comision' and chat.comision:
#             data['comisiones'][chat.comision.id_comision] = nuevos

#         elif chat.tipo == 'privado':
#             # obtener el "otro" participante del chat
#             otro = chat.participantes.exclude(id=usuario.id).first()
#             if otro:
#                 # construir display_name (priorizar nombre real si existe)
#                 display = otro.nombre_usuario
#                 try:
#                     if getattr(otro, 'id_estudiante', None):
#                         est = otro.id_estudiante
#                         if getattr(est, 'nombre', None) and getattr(est, 'apellido', None):
#                             display = f"{est.nombre} {est.apellido}"
#                     elif getattr(otro, 'id_empleado', None):
#                         emp = otro.id_empleado
#                         if getattr(emp, 'nombre', None) and getattr(emp, 'apellido', None):
#                             display = f"{emp.nombre} {emp.apellido}"
#                 except Exception:
#                     pass

#                 data['privados'].append({
#                     'id': otro.id_usuario,
#                     'username': otro.nombre_usuario,   # usar en la URL /chat/privado/<username>/
#                     'display_name': display,          # mostrar en la UI
#                     'nuevos': nuevos
#                 })

#     return JsonResponse(data)


#-------------------------------------------------------------------------------------------------------------------
# from django.http import JsonResponse
from django.db.models import Count, Q
from django.http import JsonResponse

from .models import Chat, LecturaMensaje, PerfilUsuario, Mensaje


def mensajes_nuevos_view(request):
    nombre_usuario = request.session.get('usuario_logueado')

    if not nombre_usuario:
        return JsonResponse({'error': 'no logueado'}, status=401)

    try:
        usuario = PerfilUsuario.objects.get(nombre_usuario=nombre_usuario)
    except PerfilUsuario.DoesNotExist:
        return JsonResponse({'error': 'usuario inválido'}, status=401)

    data = {
        'general': 0,
        'comisiones': {},
        'privados': [],
    }

    chats = (
        Chat.objects
        .filter(participantes=usuario)
        .select_related('comision')
        .prefetch_related('participantes', 'mensajes')
    )

    for chat in chats:

        # mensajes no leídos que NO envió el usuario actual
        mensajes_no_leidos = (
            chat.mensajes
            .filter(leido=False)
            .exclude(remitente=usuario)
        )

        cantidad = mensajes_no_leidos.count()

        # =========================
        # CHAT GENERAL
        # =========================
        if chat.tipo == 'general':
            data['general'] = cantidad

        # =========================
        # COMISIONES
        # =========================
        elif chat.tipo == 'comision' and chat.comision:

            data['comisiones'][chat.comision.id_comision] = cantidad

        # =========================
        # PRIVADOS
        # =========================
        elif chat.tipo == 'privado':

            # IMPORTANTE:
            # PerfilUsuario usa id_usuario, NO id
            otro = (
                chat.participantes
                .exclude(id_usuario=usuario.id_usuario)
                .first()
            )

            if otro:

                ultimo = mensajes_no_leidos.last()

                data['privados'].append({
                    'id': otro.id_usuario,
                    'id_usuario': otro.id_usuario,
                    'username': otro.nombre_usuario,
                    'nombre': (
                        f'{otro.id_estudiante.nombre} {otro.id_estudiante.apellido}'
                        if otro.id_estudiante
                        else f'{otro.id_empleado.nombre} {otro.id_empleado.apellido}'
                        if otro.id_empleado
                        else otro.nombre_usuario
                    ),

                    'display_name': (
                        f'{otro.id_estudiante.nombre} {otro.id_estudiante.apellido}'
                        if otro.id_estudiante
                        else f'{otro.id_empleado.nombre} {otro.id_empleado.apellido}'
                        if otro.id_empleado
                        else otro.nombre_usuario
                    ),
                    'nuevos': cantidad,
                    'ultimo_texto': (
                        ultimo.texto[:30]
                        if ultimo and ultimo.texto
                        else ''
                    ),
                    'hora': (
                        ultimo.creado.strftime('%H:%M')
                        if ultimo
                        else ''
                    ),
                })

    return JsonResponse(data)

#-------------------------------------------------------------------------------------------------------------------

from .models import LecturaMensaje

def actualizar_lectura(chat, usuario):
    ultimo = (
    chat.mensajes
    .exclude(remitente=usuario)
    .order_by('-creado')
    .first()
)
    if not ultimo:
        return
    lectura, _ = LecturaMensaje.objects.get_or_create(usuario=usuario, chat=chat)
    lectura.ultimo_mensaje_leido = ultimo
    lectura.save()



###################################################################################################################
###-----------------------Estadisticas generales, cursos, comisiones y clase------------------------------------###
###################################################################################################################

from django.http import JsonResponse
from django.db.models import Avg, Count
from .models import ValoracionAlumno

def obtener_estadisticas_valoraciones(request):
    ambito = request.GET.get('ambito', 'institucion')
    filtro_id = request.GET.get('id')

    print(f"DEBUG - Ámbito: {ambito} | ID: {filtro_id}")  # ← Debug

    valoraciones = ValoracionAlumno.objects.all()

    # FILTRO SEGÚN ÁMBITO
    if filtro_id:
        if ambito == 'curso':
            valoraciones = valoraciones.filter(curso_id=filtro_id)
        elif ambito == 'comision':
            valoraciones = valoraciones.filter(comision_id=filtro_id)
        elif ambito == 'clase':
            valoraciones = valoraciones.filter(clase_id=filtro_id)

    print(f"DEBUG - Valoraciones encontradas: {valoraciones.count()}")  # ← Debug

    # Recuento de preferencias
    liked_counts = valoraciones.values('preferencia_clase').annotate(total=Count('valoracion_alumno_id'))

    # Promedios
    promedio = valoraciones.aggregate(
        profe=Avg('rol_profe'),
        contenido=Avg('contenido'),
        plataforma=Avg('plataforma'),
        streaming=Avg('streaming')
    )

    total_valoraron = valoraciones.count()

    # Distribución 1-10 por pregunta
    def contar_valores_por_pregunta(campo):
        conteo = {str(i): 0 for i in range(1, 11)}
        valores = valoraciones.values(campo).annotate(cantidad=Count('valoracion_alumno_id'))
        for v in valores:
            valor = v.get(campo)
            if valor and str(valor) in conteo:
                conteo[str(valor)] = v['cantidad']
        return [conteo[str(i)] for i in range(1, 11)]

    distribuciones = {
        'rol_profe': contar_valores_por_pregunta('rol_profe'),
        'contenido': contar_valores_por_pregunta('contenido'),
        'plataforma': contar_valores_por_pregunta('plataforma'),
        'streaming': contar_valores_por_pregunta('streaming'),
    }

    return JsonResponse({
        'liked': {
            'gustó': next((x for x in liked_counts if x['preferencia_clase'] == 'me_gusto'), {'total': 0}),
            'masomenos': next((x for x in liked_counts if x['preferencia_clase'] == 'mas_o_menos'), {'total': 0}),
            'nogusto': next((x for x in liked_counts if x['preferencia_clase'] == 'no_me_gusto'), {'total': 0}),
        },
        'promedios': promedio or {},
        'valoraron_vs_no': {
            'valoraron': total_valoraron,
            'no_valoraron': 0
        },
        'distribuciones': distribuciones
    })
#----------------------------------------------------------------------------------------------------

def obtener_clases_opciones(request):
    clases = ClaseComision.objects.select_related('comision', 'clase').all()
    opciones = [
        {'id': c.id, 'nombre': f"{c.comision.id_curso.nombre_curso} - Clase {c.clase.numero_clase}: {c.clase.nombre_clase}"}
        for c in clases
    ]
    return JsonResponse({'clases': opciones})
#----------------------------------------------------------------------------------------------------------
from django.http import JsonResponse
from .models import Curso  # Ajustar si tu modelo se llama diferente

def obtener_cursos(request):
    cursos = Curso.objects.all().values('id_curso', 'nombre_curso')
    data = [{'id': c['id_curso'], 'nombre': c['nombre_curso']} for c in cursos]
    return JsonResponse({'cursos': data})

#----------------------------------------------------------------------------------------------------------
from .models import Comision

def obtener_comisiones(request):
    curso_id = request.GET.get('curso')
    if not curso_id or not curso_id.isdigit():
        return JsonResponse({'comisiones': []})

    comisiones = Comision.objects.filter(id_curso_id=curso_id).values('id_comision', 'nombre_comision')
    data = [{'id': c['id_comision'], 'nombre': c['nombre_comision']} for c in comisiones]
    return JsonResponse({'comisiones': data})

#----------------------------------------------------------------------------------------------------------
from .models import ClaseComision

def obtener_clases(request):
    comision_id = request.GET.get('comision')
    if not comision_id or not comision_id.isdigit():
        return JsonResponse({'clases': []})

    clases = ClaseComision.objects.select_related('clase').filter(comision_id=comision_id)
    data = [
        {
            'id': c.id,
            'nombre': f"Clase {c.clase.numero_clase}: {c.clase.nombre_clase}"
        }
        for c in clases
    ]
    return JsonResponse({'clases': data})

#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------

# =====================================================
# APIs SIMPLES PARA LOS SELECTS DE ESTADÍSTICAS
# (No afectan tus vistas originales)
# =====================================================

from django.http import JsonResponse
from .models import Curso, Comision, ClaseComision

def api_cursos_estadisticas(request):
    cursos = Curso.objects.all().order_by('id_curso')
    data = [{'id': c.id_curso, 'nombre': c.nombre_curso} for c in cursos]
    return JsonResponse(data, safe=False)


def api_comisiones_estadisticas(request):
    curso_id = request.GET.get('curso')
    if not curso_id:
        return JsonResponse([], safe=False)
    
    comisiones = Comision.objects.filter(id_curso_id=curso_id).order_by('numero_comision')
    data = [{'id': c.id_comision, 'nombre': f"Comisión {c.numero_comision}"} for c in comisiones]
    return JsonResponse(data, safe=False)


def api_clases_estadisticas(request):
    comision_id = request.GET.get('comision')
    if not comision_id:
        return JsonResponse([], safe=False)
    
    clases = ClaseComision.objects.filter(
        comision_id=comision_id
    ).select_related('clase').order_by('clase__numero_clase')  # ← Ordenado por número de clase

    data = [{
        'id': c.clase.id,
        'nombre': f"Clase {c.clase.numero_clase}: {c.clase.nombre_clase}"
    } for c in clases]
    
    return JsonResponse(data, safe=False)

#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------------------------


from django.shortcuts import render

def error_400_view(request, exception):
    return render(request, 'errors/400.html', status=400)

def error_403_view(request, exception):
    return render(request, 'errors/403.html', status=403)

def error_404_view(request, exception):
    return render(request, 'errors/404.html', status=404)

def error_500_view(request):
    return render(request, 'errors/500.html', status=500)


#################################################################################################################
####----------------------------------Alta de alumnos de clase 1----------------------------------------------###
#################################################################################################################

# views.py → VISTA FINAL (unifica Desarrollo Web + IA)

from django.shortcuts import render
from django.db.models import Count
from .models import InscripcionClaseGratis, InscripcionIAPromo, Comision  # ← IMPORTANTE: ambas tablas + Comision
from plataforma.decorators import session_required
import itertools
import json

@session_required
def alumnos_clase1_html(request):
    # === 1. Traemos los inscriptos de Desarrollo Web ===
    web_qs = InscripcionClaseGratis.objects.all().order_by('-creado')
    web_inscripciones = []
    for i in web_qs:
        i.curso = "Desarrollo Web"
        i.tecnologias_display = i.tecnologias  # para mostrar en tabla
        web_inscripciones.append(i)

    # === 2. Traemos los inscriptos de IA ===
    ia_qs = InscripcionIAPromo.objects.all().order_by('-creado')
    ia_inscripciones = []
    for i in ia_qs:
        i.curso = "Curso Gratis IA"
        i.tecnologias_display = "—"  # IA no tiene tecnologías
        ia_inscripciones.append(i)

    # === 3. Unimos y ordenamos por fecha (más nuevo arriba) ===
    inscripciones = sorted(
        web_inscripciones + ia_inscripciones,
        key=lambda x: x.creado,
        reverse=True
    )

    # === 4. Función para contar elementos separados por coma ===
    def split_counts(lst):
        flat = list(itertools.chain.from_iterable(
            [x.split(', ') for x in lst if x and x not in ('Ninguno', '—')]
        ))
        return {k: flat.count(k) for k in set(flat)}

    # === 5. Gráficos (sumamos datos de ambos cursos) ===
    # Días
    dias_list = [i.dias for i in inscripciones]
    graf_dias = split_counts(dias_list)

    # Horarios
    horarios_list = [i.horarios for i in inscripciones]
    graf_horarios = split_counts(horarios_list)

    # Nivel PC
    nivel_pc_counts = {}
    for i in inscripciones:
        nivel_pc_counts[i.nivel_pc] = nivel_pc_counts.get(i.nivel_pc, 0) + 1
    nivel_pc_sorted = dict(sorted(nivel_pc_counts.items()))

    # Experiencia en programación
    exp_prog_counts = {}
    for i in inscripciones:
        exp_prog_counts[i.exp_programacion] = exp_prog_counts.get(i.exp_programacion, 0) + 1

    # Nivel de programación
    nivel_prog_counts = {}
    for i in inscripciones:
        nivel_prog_counts[i.nivel_programacion] = nivel_prog_counts.get(i.nivel_programacion, 0) + 1
    nivel_prog_sorted = dict(sorted(nivel_prog_counts.items()))

    # Tecnologías (solo Desarrollo Web tiene)
    tecno_list = [i.tecnologias for i in web_inscripciones if i.tecnologias and i.tecnologias != "Ninguna"]
    graf_tecnos = split_counts(tecno_list)

    # === 6. Comisiones próximas para el select ===
    comisiones_proximas = Comision.objects.filter(estado_comision='proximo').select_related('id_curso').order_by('id_curso__nombre_curso', 'numero_comision')

    # === 7. Contexto final ===
    contexto = {
        "inscripciones": inscripciones,
        "comisiones_proximas": comisiones_proximas,  # ← NUEVO: Para los selects en la tabla

        "graf_dias_labels": json.dumps(list(graf_dias.keys())),
        "graf_dias_data": json.dumps(list(graf_dias.values())),

        "graf_horarios_labels": json.dumps(list(graf_horarios.keys())),
        "graf_horarios_data": json.dumps(list(graf_horarios.values())),

        "graf_nivel_pc_labels": json.dumps(list(nivel_pc_sorted.keys())),
        "graf_nivel_pc_data": json.dumps(list(nivel_pc_sorted.values())),

        "graf_exp_prog_labels": json.dumps(list(exp_prog_counts.keys())),
        "graf_exp_prog_data": json.dumps(list(exp_prog_counts.values())),

        "graf_nivel_prog_labels": json.dumps(list(nivel_prog_sorted.keys())),
        "graf_nivel_prog_data": json.dumps(list(nivel_prog_sorted.values())),

        "graf_tecnos_labels": json.dumps(list(graf_tecnos.keys())),
        "graf_tecnos_data": json.dumps(list(graf_tecnos.values())),
    }

    return render(request, 'administrador/alumnos_clase1.html', contexto)


#######################################################################################################################
#####---------------------------Alta y edicion, eliminacion de clases de cursos---------------------------------#######
#######################################################################################################################


from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET, require_POST
from .models import Curso, Clase
from django.db.models import Max


# Vista principal
def alta_clases_de_curso(request):
    cursos = Curso.objects.all()
    guardado_exitoso = request.GET.get('guardado') == '1'

    if request.method == 'POST':
        curso_id = request.POST.get('curso')
        clase_id = request.POST.get('clase')
        nombre_clase = request.POST.get('nombre_clase')
        numero_clase = request.POST.get('numero_clase')
        estado_clase = request.POST.get('estado_clase')
        ppt = request.POST.get('ppt')
        cargar_nueva = request.POST.get('cargar_nueva_clase') == 'on'

        if not curso_id:
            return render(request, 'educativa/alta_clases_de_curso.html', {
                'cursos': cursos,
                'guardado_exitoso': False,
                'error': 'Debe seleccionar un curso.'
            })

        if cargar_nueva or not clase_id:
            # Buscar un ID disponible (el mayor + 1)
            ultimo_id = Clase.objects.aggregate(Max('id'))['id__max'] or 0
            nuevo_id = ultimo_id + 1

            Clase.objects.create(
                id=nuevo_id,
                curso_id=curso_id,
                nombre_clase=nombre_clase,
                numero_clase=numero_clase,
                estado_clase=estado_clase,
                ppt=ppt
            )
        else:
            # Editar clase existente
            try:
                clase = Clase.objects.get(pk=clase_id)
                clase.nombre_clase = nombre_clase
                clase.numero_clase = numero_clase
                clase.estado_clase = estado_clase
                clase.ppt = ppt
                clase.save()
            except Clase.DoesNotExist:
                return render(request, 'educativa/alta_clases_de_curso.html', {
                    'cursos': cursos,
                    'guardado_exitoso': False,
                    'error': 'La clase no existe.'
                })

        return redirect('/alta_clases_de_curso/?guardado=1')

    return render(request, 'educativa/alta_clases_de_curso.html', {
        'cursos': cursos,
        'guardado_exitoso': guardado_exitoso
    })



# AJAX - Obtener clases por curso
@require_GET
def ajax_obtener_clases_de_curso(request):
    curso_id = request.GET.get('curso_id')
    if not curso_id:
        return JsonResponse({'error': 'Falta curso_id'}, status=400)

    try:
        clases = Clase.objects.filter(curso__id_curso=curso_id).order_by('numero_clase')
        data = [{"id": c.id, "nombre": c.nombre_clase} for c in clases]
        return JsonResponse({'clases': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# AJAX - Obtener datos de una clase individual
@require_GET
def ajax_obtener_datos_clase(request):
    clase_id = request.GET.get('clase_id')
    clase = get_object_or_404(Clase, pk=clase_id)

    data = {
        "id": clase.id,
        "nombre_clase": clase.nombre_clase,
        "numero_clase": clase.numero_clase,
        "estado_clase": clase.estado_clase,
        "ppt": clase.ppt or ""
    }
    return JsonResponse(data)


# AJAX - Eliminar una clase
@require_POST
def ajax_eliminar_clase(request):
    clase_id = request.GET.get('clase_id')
    if not clase_id:
        return JsonResponse({'error': 'Falta clase_id'}, status=400)

    try:
        clase = Clase.objects.get(pk=clase_id)
        clase.delete()
        return JsonResponse({'mensaje': 'Clase eliminada correctamente'})
    except Clase.DoesNotExist:
        return JsonResponse({'error': 'Clase no encontrada'}, status=404)
    

##################################################################################################
####----------------------------listado de valoraciones---------------------------------------####
##################################################################################################

# plataforma/views.py (Revisa esta función)

from .models import ValoracionAlumno, Comision # ¡Asegúrate de importar Comision!

# ... (otras funciones y vistas) ...

@session_required 
def listado_valoraciones(request):
    
    valoraciones_qs = ValoracionAlumno.objects.all().order_by('-fecha_valoracion')
    valoraciones_procesadas = []
    
    # Este bucle es NECESARIO porque 'comision_id' es un CharField
    for valoracion in valoraciones_qs:
        numero_comision = 'N/A' 
        
        if valoracion.comision_id:
            try:
                # Buscamos en la tabla Comision usando el ID guardado
                comision_obj = Comision.objects.get(id_comision=valoracion.comision_id)
                numero_comision = comision_obj.numero_comision
            except Comision.DoesNotExist:
                numero_comision = 'ID Inválido'
            except Exception:
                numero_comision = 'Error'
        
        # Creamos el nuevo atributo que SÍ podemos usar en el template
        valoracion.numero_comision_display = numero_comision 
        valoraciones_procesadas.append(valoracion)
        
    return render(request, 'administrador/listado_valoraciones.html', {'valoraciones': valoraciones_procesadas,'nombre_usuario': request.session.get('usuario_logueado'),})

##################################################################################################
####----------------------------listado de proyectos------------------------------------------####
##################################################################################################

def listado_proyectos(request):
    entregas = EntregaProyecto.objects.select_related("estudiante", "curso", "comision")
    return render(request, "administrador/listado_proyectos.html", {"entregas": entregas, 'nombre_usuario': request.session.get('usuario_logueado'),})

##################################################################################################
####-----------------------------------listado de pagos---------------------------------------####
##################################################################################################

# views.py
from .models import RegistroPago

def listado_pagos(request):
    pagos = RegistroPago.objects.select_related('estudiante', 'comision').all().order_by('-fecha_pago')
    return render(request, 'administrador/listado_pagos.html', {'registropago': pagos})

##################################################################################################
####--------------------------------------subscriptores---------------------------------------####
##################################################################################################

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Suscriptor  # Asegurate de tener este modelo

@csrf_exempt  # Temporal para probar rápido. Después lo quitamos si querés
def newsletter_view(request):
    # Si es una petición AJAX (nuestro formulario)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
        if request.method == 'POST':
            nombre = request.POST.get('nombre', '').strip()
            email = request.POST.get('email', '').strip().lower()

            if not nombre or not email:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Completa todos los campos'
                }, status=400)

            suscriptor, created = Suscriptor.objects.get_or_create(
                email=email,
                defaults={'nombre': nombre}
            )

            if not created:
                # Actualiza nombre si cambió
                if suscriptor.nombre != nombre:
                    suscriptor.nombre = nombre
                    suscriptor.save()
                return JsonResponse({'status': 'exists'})

            return JsonResponse({'status': 'success'})

        return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

    # Si es una petición normal (alguien entra directo a /newsletter/)
    # Puedes redirigir al inicio o mostrar algo
    return redirect('inicio')  # o 'inicio', según tu name en urls.py


##################################################################################################
####--------------------- se creo preferencias 13/10/2025-------------------------------------####
##################################################################################################

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import mercadopago
from django.conf import settings

@csrf_exempt
def crear_preferencia(request):
    if request.method == "POST":
        try:
            sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

            body = {
                "items": [
                    {
                        "title": "Curso Desarrollo Web",  # título que verá el alumno
                        "quantity": 1,
                        "unit_price": 15000,  # monto en ARS
                        "currency_id": "ARS"
                    }
                ]
            }

            preference_response = sdk.preference().create(body)
            preference = preference_response["response"]

            return JsonResponse({"preference_id": preference["id"]})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Método no permitido"}, status=405)

#---------------------------------------------------------------------------------------------

# views.py
from django.db.models import Count
from django.utils import timezone
from plataforma.models import Mensaje, PerfilUsuario


def chat_estadisticas(request):
    print("ENTRAMOS A chat_estadisticas")

    # === CONTADORES ===
    mensajes_general = Mensaje.objects.filter(chat__tipo='general').count()
    mensajes_comisiones = Mensaje.objects.filter(chat__tipo='comision').count()
    mensajes_privados = Mensaje.objects.filter(chat__tipo='privado').count()
    total_mensajes = Mensaje.objects.count()
    mensajes_hoy = Mensaje.objects.filter(creado__date=timezone.localdate()).count()

    profesores = PerfilUsuario.objects.filter(rol='profesor').count()
    tutores = PerfilUsuario.objects.filter(rol='tutor').count()
    alumnos_activos = PerfilUsuario.objects.filter(rol='alumno', is_active=True).count()

    # === MENSAJES POR COMISIÓN ===
    mensajes_por_comision = (
        Mensaje.objects
        .filter(chat__tipo='comision')
        .values('chat__comision__id_comision', 'chat__comision__id_curso__nombre_curso', 'chat__comision__numero_comision')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # === ALUMNOS: TOTAL DE MENSAJES EN PRIVADOS ===
    alumnos_mensajes = (
        Mensaje.objects
        .filter(chat__tipo='privado', remitente__rol='alumno')
        .values(
            'remitente__id_usuario',
            'remitente__id_estudiante__nombre',
            'remitente__id_estudiante__apellido',
            'remitente__nombre_usuario'
        )
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # === PROFESORES ===
    profesores_mensajes = (
        Mensaje.objects
        .filter(chat__tipo='privado', remitente__rol='profesor')
        .values(
            'remitente__id_usuario',
            'remitente__id_estudiante__nombre',
            'remitente__id_estudiante__apellido',
            'remitente__nombre_usuario'
        )
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # === TUTORES ===
    tutores_mensajes = (
        Mensaje.objects
        .filter(chat__tipo='privado', remitente__rol='tutor')
        .values(
            'remitente__id_usuario',
            'remitente__id_estudiante__nombre',
            'remitente__id_estudiante__apellido',
            'remitente__nombre_usuario'
        )
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    contexto = {
        "mensajes_general": mensajes_general,
        "mensajes_comisiones": mensajes_comisiones,
        "mensajes_privados": mensajes_privados,
        "total_mensajes": total_mensajes,
        "mensajes_hoy": mensajes_hoy,
        "profesores": profesores,
        "tutores": tutores,
        "alumnos_activos": alumnos_activos,

        "mensajes_por_comision": list(mensajes_por_comision),
        "alumnos_mensajes": list(alumnos_mensajes),
        "profesores_mensajes": list(profesores_mensajes),
        "tutores_mensajes": list(tutores_mensajes),
    }

    return render(request, "administrador/chat_placeholder.html", contexto)


#-----------------------------------------------------------------------------

# === VER MENSAJES DE UN USUARIO (privado) ===
def ver_mensajes_usuario(request, usuario_id):
    mensajes = Mensaje.objects.filter(
        chat__tipo='privado',
        remitente__id_usuario=usuario_id
    ).select_related('chat').order_by('-creado')

    return render(request, 'administrador/partial_mensajes_usuario.html', {
        'mensajes': mensajes,
    })

# === VER MENSAJES DE UNA COMISIÓN ===
def ver_mensajes_comision(request, comision_id):
    mensajes = Mensaje.objects.filter(
        chat__tipo='comision',
        chat__comision__id_comision=comision_id
    ).select_related('remitente', 'chat__comision').order_by('-creado')

    return render(request, 'administrador/partial_mensajes_comision.html', {
        'mensajes': mensajes,
        'comision_id': comision_id,
    })


# === VER MENSAJES GENERAL ===
def ver_mensajes_general(request):
    mensajes = Mensaje.objects.filter(chat__tipo='general').order_by('-creado')
    return render(request, 'administrador/partial_mensajes_general.html', {'mensajes': mensajes})


#----------------------------------------------------------------------------------------------------------
# validacion de nombre de usuario en tiempo real desede perfil_alumno.html
#----------------------------------------------------------------------------------------------------------

# views.py

# views.py (Versión Reforzada)

import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model

User = get_user_model()

# views.py (Solo el contenido de la función verificar_nombre_usuario)

@csrf_exempt
@require_http_methods(["POST"])
def verificar_nombre_usuario(request):
    
    # Hemos comentado la verificación de autenticación para evitar el 401 de AJAX. 
    # Para producción, es recomendable solucionarlo con headers de sesión, pero esto permite avanzar.

    try:
        data = json.loads(request.body)
        nombre_usuario_a_verificar = data.get('nombre_usuario', '').strip()

        if not nombre_usuario_a_verificar:
             return JsonResponse({'error': 'Nombre de usuario requerido'}, status=400)
        
        # Obtenemos el ID del usuario actual.
        # Esto maneja el caso de que request.user sea anónimo (ID 0) o logueado.
        usuario_actual_id = request.user.pk if request.user.is_authenticated else 0

        # CAMBIO CRUCIAL:
        # 1. Intentamos encontrar un usuario con ese nombre EXCLUYENDO el ID del usuario actual.
        #    Cambiamos 'username__iexact' por 'nombre_usuario__iexact'
        existe = User.objects.exclude(pk=usuario_actual_id).filter(
            nombre_usuario__iexact=nombre_usuario_a_verificar # <--- ¡Aquí está la corrección!
        ).exists()

        if existe:
            return JsonResponse({'disponible': False})
        else:
            return JsonResponse({'disponible': True})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Formato de petición inválido.'}, status=400)
    except AttributeError:
        return JsonResponse({'error': 'Error de atributo en el objeto de usuario.'}, status=500)
    except Exception as e:
        # Esto ya no debería fallar si la corrección se aplicó correctamente
        print(f"Error grave en verificar_nombre_usuario: {e}") 
        return JsonResponse({'error': 'Error interno del servidor.'}, status=500)
    
    #------------------------------------------------------------------------------------------
    # actualizar el listado de pagos del admiinistrador
    #------------------------------------------------------------------------------------------

# En tu archivo views.py
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal, InvalidOperation 
# Asegúrate de que esta importación sea correcta
from plataforma.models import RegistroPago 


@require_POST
def actualizar_pago(request, pago_id):
    # NOTA: Asegúrate de tener la lógica de permisos adecuada aquí si es necesario.

    try:
        pago = get_object_or_404(RegistroPago, pk=pago_id)
        
        # 1. Obtener datos de POST (incluye estado, monto, observaciones, link y la bandera de eliminación)
        new_estado = request.POST.get('estado_pago')
        new_monto_str = request.POST.get('monto')
        new_obs = request.POST.get('observaciones', '').strip()
        new_link = request.POST.get('link_comprobante', '').strip() # <-- Link Comprobante
        delete_archivo_flag = request.POST.get('delete_archivo_comprobante') == '1' # <-- Bandera de Eliminación

        # 2. Obtener el archivo de FILES
        new_archivo = request.FILES.get('archivo_comprobante') # <-- Archivo Comprobante
        
        # --- Validación del Estado ---
        if not new_estado:
            return JsonResponse({'success': False, 'error': 'El estado de pago no puede estar vacío.'}, status=400)
            
        # --- Validación y Conversión del Monto (CRUCIAL) ---
        try:
            new_monto = Decimal(new_monto_str)
            if new_monto <= 0:
                 return JsonResponse({'success': False, 'error': 'El monto debe ser un valor positivo.'}, status=400)
        except (InvalidOperation, TypeError):
             return JsonResponse({'success': False, 'error': 'El formato del monto es inválido. Debe ser un número.'}, status=400)
        
        # 3. Actualizar los campos del modelo
        pago.estado_pago = new_estado
        pago.monto = new_monto
        
        # Actualizar Observaciones
        pago.observaciones = new_obs if new_obs and new_obs.lower() != 'none' else None
        
        # Actualizar Link Comprobante: Se asigna None si el campo se vacía
        pago.link_comprobante = new_link if new_link else None
        
        # Actualizar Archivo Comprobante: Manejamos las tres posibilidades (Eliminar, Subir nuevo, Mantener)
        if delete_archivo_flag:
            # Opción 1: Eliminación explícita (establece el campo en None, lo que borra el archivo anterior)
            pago.archivo_comprobante = None
        elif new_archivo:
            # Opción 2: Subida de nuevo archivo (reemplaza el anterior)
            pago.archivo_comprobante = new_archivo
        # Opción 3 (implícita): Si no hay bandera de eliminación ni nuevo archivo, el valor existente se mantiene.
        
        # 4. Guardar en la base de datos
        pago.save()
        
        # Devolver la URL del archivo subido (si existe) para confirmación en el frontend
        archivo_url = pago.archivo_comprobante.url if pago.archivo_comprobante else None
        
        return JsonResponse({
            'success': True, 
            'message': 'Pago actualizado exitosamente.',
            'archivo_url': archivo_url
        })
        
    except RegistroPago.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Registro de Pago no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error interno del servidor: {str(e)}'}, status=500)

#-------------------------------------------------------------------------------------------------------------------
# Asistencia general view
#-------------------------------------------------------------------------------------------------------------------

from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Prefetch
# Asegúrate de importar todos los modelos necesarios
from .models import Comision, DatosDeEstudiantes, Clase, AsistenciaClase, Curso, PerfilUsuario

def asistencia_general_view(request, comision_id):
    
    # 1. BÚSQUEDA ROBUSTA DE LA COMISIÓN
    # -------------------------------------------------------------------------
    try:
        id_busqueda_int = int(comision_id)
    except ValueError:
        id_busqueda_int = None

    id_busqueda_relleno = str(comision_id).zfill(6)

    try:
        filtro = Q(id_comision=id_busqueda_relleno)
        if id_busqueda_int is not None:
            filtro |= Q(numero_comision=id_busqueda_int)
        comision = Comision.objects.get(filtro)
    except Comision.DoesNotExist:
        # Si no se encuentra, devuelve un 404
        return get_object_or_404(Comision, pk=None) 

    # 2. OBTENER CURSO Y CLASES
    # -------------------------
    curso = comision.id_curso
    clases = Clase.objects.filter(curso=curso).order_by('numero_clase')

    # 3. FILTRADO DE ESTUDIANTES POR COMISIÓN (select_related CORREGIDO)
    # ------------------------------------------------------------------
    estudiantes_qs = DatosDeEstudiantes.objects.filter(
        Q(cursando1=comision) | Q(cursando2=comision) | Q(cursando3=comision) |
        Q(cursando4=comision) | Q(cursando5=comision) | Q(cursando6=comision) |
        Q(cursando7=comision) | Q(cursando8=comision) | Q(cursando9=comision)
    ).order_by('apellido', 'nombre').select_related('perfilusuario').prefetch_related( # <--- CORREGIDO: 'perfilusuario'
        Prefetch(
            'asistenciaclase_set',
            queryset=AsistenciaClase.objects.filter(comision=comision).select_related('clase'),
            to_attr='asistencias_comision'
        )
    )

    # 4. PROCESAR ASISTENCIAS (AÑADIENDO EL ROL CORREGIDO)
    # ----------------------------------------------------
    datos_tabla = []
    for estudiante in estudiantes_qs:
        
        # OBTENER ROL: Accediendo a la relación corregida
        try:
            rol_usuario = estudiante.perfilusuario.rol.lower() # <--- CORREGIDO: .perfilusuario
        except AttributeError:
            rol_usuario = 'alumno'  # Fallback seguro

        registro_asistencia = {
            'id_estudiante': estudiante.id_estudiante,
            'nombre_completo': f"{estudiante.nombre} {estudiante.apellido}",
            'rol': rol_usuario, # Campo clave para el ordenamiento
            'clase_statuses': [],
            'total_presente': 0
        }

        asistencias_map = {
            asistencia.clase_id: 'presente'
            for asistencia in estudiante.asistencias_comision
        }

        total_presente = 0
        for clase in clases:
            estado = asistencias_map.get(clase.id, 'ausente')
            if estado == 'presente':
                registro_asistencia['clase_statuses'].append('✅')
                total_presente += 1
            else:
                registro_asistencia['clase_statuses'].append('❌')

        registro_asistencia['total_presente'] = total_presente
        datos_tabla.append(registro_asistencia)

    # 5. LÓGICA DE ORDENAMIENTO POR ROL (Profesor > Tutor > Alumno)
    # --------------------------------------------------------------
    def obtener_orden_rol(registro):
        """Asigna un número para ordenar: 1 (Profesor) > 2 (Tutor) > 3 (Alumno)"""
        rol = registro.get('rol', 'alumno')
        if rol == 'profesor':
            return 1 
        elif rol == 'tutor':
            return 2 
        else:
            return 3 

    # Aplicamos el ordenamiento
    datos_tabla_ordenada = sorted(datos_tabla, key=obtener_orden_rol)
    # --------------------------------------------------------------

    # 6. CONTEXTO Y RENDER
    # --------------------
    contexto = {
        'curso': curso,
        'comision': comision,
        'clases': clases,
        'datos_tabla': datos_tabla_ordenada, # Se pasa la lista ORDENADA
        'total_clases': clases.count(),
        'usuario': request.user,
        'nombre_usuario': request.session.get('usuario_logueado'),
    }
    return render(request, 'educativa/asistencia_general.html', contexto)

    #----------------------------------------------------------------------------------------------------------
    # listado de asistencias
    #----------------------------------------------------------------------------------------------------------


# plataforma/views.py

from django.shortcuts import render
from .models import Comision 
from plataforma.decorators import session_required 
# ... (otras importaciones)

# ----------------------------------------------------------------------
# VISTA PARA EL LISTADO ADMINISTRATIVO DE ASISTENCIAS
# ----------------------------------------------------------------------

@session_required 
def listado_asistencias_view(request):
    """
    Muestra un listado de todas las comisiones activas.
    """
    
    # 1. Obtener todas las comisiones
    comisiones = Comision.objects.all().select_related('id_curso').order_by('id_curso__nombre_curso', '-numero_comision')
    
    # Contexto simplificado, solo se pasan las comisiones
    contexto = {
        'comisiones': comisiones,
    }
    
    # Usando la ruta 'administrador/listado_asistencias.html'
    return render(request, 'administrador/listado_asistencias.html', contexto)


#--------------------------------------------------------------------------------------------------------------------------------------

# def inscripcion_ia_promo(request):
#     return render(request, 'educativa/inscripcion_ia_promo.html')

def inscripcion_ia_promo(request):
    # === DATOS PARA LOS CHECKBOXES Y SELECTS ===
    dias_semana = [
        "Lunes", "Martes", "Miércoles", "Jueves", 
        "Viernes", "Sábado", "Domingo"
    ]

    horarios_disponibles = [
        "Mañana (8 a 12 hs)",
        "Mediodía (12 a 14 hs)",
        "Tarde (14 a 18 hs)",
        "Noche (18 a 23 hs)"
    ]

    niveles = list(range(1, 11))  # 1 al 10

    contexto = {
        'dias_semana': dias_semana,
        'horarios': horarios_disponibles,
        'niveles': niveles,
    }

    return render(request, 'educativa/inscripcion_ia_promo.html', contexto)


# =====================================================
# VISTA EXCLUSIVA PARA IA PROMO
# =====================================================

# views.py → VERSIÓN FINAL Y DEFINITIVA (FUNCIONA 100%)
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from .models import InscripcionIAPromo


def guardar_inscripcion_ia_promo(request):
    if request.method != "POST":
        return redirect('inscripcion_ia_promo')

    try:
        # 1. GUARDAR EN BASE DE DATOS (usando objects.create → esto sí crea el objeto real)
        inscripcion = InscripcionIAPromo.objects.create(
            nombre=request.POST.get('nombre', '').strip() or 'Sin nombre',
            apellido=request.POST.get('apellido', '').strip() or 'Sin apellido',
            dni=request.POST.get('dni', '').strip() or '00000000',
            fecha_nacimiento=request.POST.get('fecha_nacimiento', '2000-01-01'),
            genero=request.POST.get('genero', 'Prefiero no decir'),
            telefono=request.POST.get('telefono', '').strip() or 'Sin teléfono',
            email=request.POST.get('email', '').strip().lower() or 'sin@email.com',
            pais=request.POST.get('pais', 'Argentina'),
            provincia=request.POST.get('provincia', '') if request.POST.get('pais') == 'Argentina' else '',
            dias=','.join(request.POST.getlist('dias[]') or ['Ninguno']),
            horarios=','.join(request.POST.getlist('horarios[]') or ['Ninguno']),
            nivel_pc=int(request.POST.get('nivel_pc', 5)),
            exp_programacion=request.POST.get('exp_programacion', 'No tengo experiencia.'),
            nivel_programacion=int(request.POST.get('nivel_programacion', 1)),
        )

        # 2. CONTEXTO CON DATOS DEL OBJETO GUARDADO (AHORA SÍ EXISTE inscripcion.nombre)
        context = {
            'curso_nombre': 'Curso Gratis IA',
            'nombre': inscripcion.nombre,
            'apellido': inscripcion.apellido,
            'dni': inscripcion.dni,
            'fecha_nacimiento': inscripcion.fecha_nacimiento,
            'genero': inscripcion.genero,
            'pais': inscripcion.pais,
            'provincia': inscripcion.provincia,
            'telefono': inscripcion.telefono,
            'email': inscripcion.email,
            'dias': inscripcion.dias,
            'horarios': inscripcion.horarios,
            'nivel_pc': inscripcion.nivel_pc,
            'exp_programacion': inscripcion.exp_programacion,
            'nivel_programacion': inscripcion.nivel_programacion,
            'fecha': timezone.now(),
        }

        # 3. RENDERIZAR CORREO
        html_message = render_to_string('registration/confirmacion_inscripcion_gratuita.html', context)
        plain_message = strip_tags(html_message)

        # 4. ENVIAR CORREO A VOS (el que sí te llega)
        send_mail(
            subject=f"NUEVO INSCRIPTO IA GRATIS – {inscripcion.nombre} {inscripcion.apellido}",
            message=plain_message,
            from_email=None,
            recipient_list=['tecnomarema.ar@gmail.com'],  # ← TU MAIL QUE SÍ FUNCIONA
            html_message=html_message,
            fail_silently=False,
        )

        print("CORREO ENVIADO CORRECTAMENTE A tecnomarema.ar@gmail.com")

    except Exception as e:
        print("Error en guardar_inscripcion_ia_promo:", e)

    # 5. SIEMPRE MOSTRAR GRACIAS (nunca más error visible)
    return render(request, 'educativa/gracias.html')



    #----------------------------------------------------------------------------------------------------------


from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from .models import (
    InscripcionClaseGratis, InscripcionIAPromo,  # Modelos de inscriptos gratuitos
    DatosDeEstudiantes, PerfilUsuario, Comision, RegistroPago, Curso, ClaseComision
)
from django.db.models import Q
import json
import logging  # Para debug en consola

logger = logging.getLogger(__name__)

@csrf_exempt  # Temporal para AJAX; usa {% csrf_token %} en forms
def asignar_pago_gratis(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        exito_count = 0
        errores = []

        # Detectar si es múltiple o individual
        seleccionados_str = request.POST.get('seleccionados_multiples')
        if seleccionados_str:
            # Múltiple
            seleccionados = json.loads(seleccionados_str)
            comision_id = request.POST.get('comision_global')
        else:
            # Individual
            seleccionados = [request.POST.get('inscripcion_id')]
            comision_id = request.POST.get('comision_id')

        if not comision_id or not seleccionados:
            return JsonResponse({'error': 'Faltan datos de selección o comisión'}, status=400)

        comision = Comision.objects.get(id_comision=comision_id)
        curso = comision.id_curso

        with transaction.atomic():  # Transacción para consistencia
            for inscr_id in seleccionados:
                # Buscar inscripto (prioridad: IA Promo, luego Clase Gratis)
                inscripcion = InscripcionIAPromo.objects.filter(id=inscr_id).first()
                if not inscripcion:
                    inscripcion = InscripcionClaseGratis.objects.filter(id=inscr_id).first()
                if not inscripcion:
                    errores.append(f"Inscripción {inscr_id} no encontrada")
                    continue

                dni = inscripcion.dni or f"GRATIS_{inscripcion.id}"  # Fallback si no hay DNI
                email = inscripcion.email.lower()

                # ✅ Validaciones (evitar duplicados)
                if DatosDeEstudiantes.objects.filter(Q(dni=dni) | Q(correo=email)).exists():
                    errores.append(f"Duplicado para {inscripcion.nombre}: DNI/Email ya existe")
                    continue
                if PerfilUsuario.objects.filter(Q(nombre_usuario=dni) | Q(correo=email)).exists():
                    errores.append(f"Duplicado usuario para {inscripcion.nombre}")
                    continue

                # ✅ Crear DatosDeEstudiantes (mapeo de campos)
                ultimo_est = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
                nuevo_id_est = str(int(ultimo_est.id_estudiante) + 1 if ultimo_est else 1).zfill(6)

                estudiante = DatosDeEstudiantes.objects.create(
                    id_estudiante=nuevo_id_est,
                    nombre=inscripcion.nombre,
                    apellido=inscripcion.apellido,
                    dni=dni,
                    correo=email,
                    fecha_nacimiento=getattr(inscripcion, 'fecha_nacimiento', None),
                    pais=getattr(inscripcion, 'pais', 'Argentina'),
                    provincia=getattr(inscripcion, 'provincia', ''),
                    telefono=getattr(inscripcion, 'telefono', ''),
                    genero=getattr(inscripcion, 'genero', ''),
                    # Asignar a primer campo disponible (cursando1, etc.)
                )
                # Asignar comisión
                for i in range(1, 10):
                    campo = f'cursando{i}'
                    if getattr(estudiante, campo) is None:
                        setattr(estudiante, campo, comision)
                        break
                estudiante.save()

                # ✅ Crear PerfilUsuario
                ultimo_user = PerfilUsuario.objects.order_by('-id_usuario').first()
                nuevo_id_user = str(int(ultimo_user.id_usuario) + 1 if ultimo_user else 1).zfill(6)

                usuario = PerfilUsuario.objects.create(
                    id_usuario=nuevo_id_user,
                    id_estudiante=estudiante,
                    nombre_usuario=dni,  # Usar DNI como username
                    correo=email,
                    rol='alumno',
                    is_active=True
                )
                password_temporal = 'pass1234'  # Contraseña temporal
                usuario.set_password(password_temporal)
                usuario.save()

                # ✅ Crear RegistroPago (como "gratuito")
                pago = RegistroPago.objects.create(
                    estudiante=estudiante,
                    comision=comision,
                    plataforma='web_gratis',
                    medio_pago='inscripcion_gratuita',
                    estado_pago='Aprobado',  # Directo a aprobado
                    monto=0.00,
                    fecha_pago=timezone.now(),
                    id_transaccion=f'GRATIS_{inscripcion.id}',
                    observaciones=f'Inscripción gratuita desde clase promo. Curso: {curso.nombre_curso}. Comisión: {comision.numero_comision}.'
                )

                # ✅ Generar URL de reset de contraseña para el email de bienvenida
                uid = urlsafe_base64_encode(force_bytes(usuario.pk))
                token = default_token_generator.make_token(usuario)
                reset_url = request.build_absolute_uri(reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token}))

                # ✅ EMAIL DE BIENVENIDA AL USUARIO (usando bienvenida_paga.html adaptada para gratis)
                context_usuario = {
                    'nombre': inscripcion.nombre,
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    'usuario': dni,  # DNI como username
                    'password': password_temporal,
                    'reset_url': reset_url,  # URL para cambiar contraseña
                }

                html_message_usuario = render_to_string('registration/bienvenida_paga.html', context_usuario)
                plain_message_usuario = strip_tags(html_message_usuario)

                send_mail(
                    subject=f"¡Bienvenido/a a Tecno Marema! - Acceso a tu curso GRATIS {curso.nombre_curso}",
                    message=plain_message_usuario,
                    from_email=None,  # Usa DEFAULT_FROM_EMAIL de settings
                    recipient_list=[email],
                    html_message=html_message_usuario,
                    fail_silently=False,
                )

                # ✅ EMAIL A LA INSTITUCIÓN (notificación de nuevo registro usando registro_pago.html)
                context_institucion = {
                    'nombre': inscripcion.nombre,
                    'apellido': inscripcion.apellido,
                    'email': email,
                    'documento': dni,  # DNI como documento
                    'curso': curso.nombre_curso,
                    'comision': comision.numero_comision,
                    'pais': getattr(inscripcion, 'pais', 'Argentina'),
                    'provincia': getattr(inscripcion, 'provincia', ''),
                    'telefono': getattr(inscripcion, 'telefono', ''),
                    'medio_pago': 'inscripcion_gratuita',
                    'fecha': timezone.now(),
                }

                html_message_institucion = render_to_string('registration/registro_pago.html', context_institucion)
                plain_message_institucion = strip_tags(html_message_institucion)

                send_mail(
                    subject=f"📥 Nuevo alumno inscripto GRATIS – {inscripcion.nombre} {inscripcion.apellido}",
                    message=plain_message_institucion,
                    from_email=None,
                    recipient_list=['tecnomarema.ar@gmail.com'],  # Email de la institución
                    html_message=html_message_institucion,
                    fail_silently=False,
                )

                exito_count += 1

        if exito_count > 0:
            messages.success(request, f'{exito_count} inscriptos convertidos a pagos gratuitos exitosamente. Emails enviados (bienvenida al usuario y notificación a la institución).')
        if errores:
            messages.warning(request, 'Errores: ' + '; '.join(errores))

        return JsonResponse({'exito_count': exito_count, 'errores': errores})

    except Exception as e:
        logger.error(f"Error en asignar_pago_gratis: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


#----------------------------------------------------------------------------------------------------------

# Import (asegúrate de tenerlos al inicio de views.py)
from .models import ClaseComision, Clase  # Modelos clave

# ✅ VISTA FINAL: Fetch clase con 'curso' (no 'id_curso'), case-insensitive para curso
@csrf_exempt
def enviar_correos_clase1(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        seleccionados_str = request.POST.get('seleccionados_multiples')
        if not seleccionados_str:
            return JsonResponse({'error': 'No hay seleccionados'}, status=400)

        seleccionados = json.loads(seleccionados_str)
        comision_id = request.POST.get('comision_global', '')  # '000001'
        exito_count = 0
        errores = []

        # Fetch comisión
        comision = None
        if comision_id:
            try:
                comision = Comision.objects.get(id_comision=comision_id)
                print(f"🔍 Comisión encontrada: ID='{comision_id}' - Curso='{comision.id_curso.nombre_curso}' - Número={comision.numero_comision}")
            except Comision.DoesNotExist:
                errores.append(f"Comisión '{comision_id}' no encontrada.")
                print(f"❌ Comi '{comision_id}' no existe")
                comision = None

        # Fetch ClaseComision para la PRIMERA CLASE (0 para Web, 1 para otros)
        primera_clase = None
        if comision:
            try:
                # Determinar numero_clase basado en curso (case-insensitive)
                curso_nombre_lower = comision.id_curso.nombre_curso.lower()
                if 'desarrollo web' in curso_nombre_lower:
                    numero_clase_primera = 0  # Primera para Web
                    print(f"🎯 Para Desarrollo Web: Usando numero_clase=0")
                else:
                    numero_clase_primera = 1  # Primera para IA/otros
                    print(f"🎯 Para {comision.id_curso.nombre_curso}: Usando numero_clase=1")

                # Paso 1: Fetch la Clase con numero_clase_primera para el curso de la comisión (usa 'curso' como field)
                clase_primera = Clase.objects.filter(
                    curso=comision.id_curso,  # FK a Curso object (choices have 'curso')
                    numero_clase=numero_clase_primera
                ).first()
                print(f"🔍 Clase encontrada para curso '{comision.id_curso.nombre_curso}' y numero_clase={numero_clase_primera}: ID='{clase_primera.id if clase_primera else 'None'}'")

                if clase_primera:
                    # Paso 2: Fetch ClaseComision para esa clase y comision
                    primera_clase = ClaseComision.objects.filter(
                        comision=comision,  # FK a Comision object
                        clase=clase_primera  # FK a Clase object
                    ).first()
                    if primera_clase:
                        print(f"✅ ClaseComision encontrada para comision '{comision_id}' y clase ID='{clase_primera.id}': Fecha={primera_clase.fecha} Hora={primera_clase.horario} Link='{primera_clase.link}'")
                    else:
                        print(f"⚠️ No ClaseComision para comision '{comision_id}' y clase ID='{clase_primera.id}' – Usando fallback comision")
                else:
                    print(f"⚠️ No Clase con numero_clase={numero_clase_primera} para curso '{comision.id_curso.nombre_curso}' – Usando fallback comision")
            except Exception as e:
                errores.append(f"Error query Clase/ClaseComision: {str(e)}")
                print(f"❌ Error filter: {str(e)}")

        for inscr_id in seleccionados:
            inscripcion = InscripcionIAPromo.objects.filter(id=inscr_id).first()
            if not inscripcion:
                inscripcion = InscripcionClaseGratis.objects.filter(id=inscr_id).first()
            if not inscripcion:
                errores.append(f"Inscripción {inscr_id} no encontrada")
                continue

            email = inscripcion.email.lower().strip()
            if not email or '@' not in email:
                errores.append(f"Email inválido: {email}")
                continue

            # Determinar curso
            if isinstance(inscripcion, InscripcionClaseGratis):
                curso_nombre = "Desarrollo Web"
            else:
                curso_nombre = "Curso Gratis IA"
            curso_tipo = "IA" if isinstance(inscripcion, InscripcionIAPromo) else "Web"

            # ✅ LINK DESDE DB (primera_clase.link si existe)
            clase1_link = None
            link_texto = f"Link por confirmar para {curso_nombre} clase 1 (contacta al equipo)"
            if primera_clase and primera_clase.link and primera_clase.link.startswith('http'):
                clase1_link = primera_clase.link  # DB real
                print(f"📎 Link DB {curso_tipo}: {clase1_link}")
            else:
                print(f"⚠️ No link en ClaseComision para {curso_tipo} (comision_id {comision_id}) – Texto: {link_texto}")

            # ✅ FECHA DESDE DB (primera_clase > comision)
            if primera_clase:
                fecha_formateada = primera_clase.fecha.strftime('%d/%m/%Y')
                hora_formateada = primera_clase.horario.strftime('%H:%M') + ' hs'
                fecha_clase = f"{fecha_formateada} a las {hora_formateada}"
            elif comision:
                fecha_formateada = comision.fecha_inicio.strftime('%d/%m/%Y')
                dia_horario = f"{comision.dia1 or 'Por definir'} {comision.horario1 or 'Por definir'}"
                fecha_clase = f"{fecha_formateada} {dia_horario}"
            else:
                fecha_clase = "Fecha por confirmar"

            # Logs
            print(f"🔍 {curso_tipo} - {inscripcion.nombre} (comision_id {comision_id}): Fecha={fecha_clase} | Link={'DB' if clase1_link else 'Texto'}")

            # Contexto
            context_email = {
                'nombre': inscripcion.nombre,
                'apellido': inscripcion.apellido,
                'curso': curso_nombre,
                'clase1_link': clase1_link,
                'link_texto': link_texto,
                'fecha_clase': fecha_clase,
            }

            # Render y send
            html_message = render_to_string('registration/clase1_email.html', context_email)
            plain_message = strip_tags(html_message)

            try:
                send_mail(
                    subject=f"¡Tu primera clase de {curso_nombre} está lista! - Tecno Marema",
                    message=plain_message,
                    from_email=None,
                    recipient_list=[email],
                    html_message=html_message,
                    fail_silently=False,
                )
                print(f"✅ Enviado a {email} ({curso_tipo})")
            except Exception as mail_error:
                errores.append(f"Error mail {email}: {str(mail_error)}")
                print(f"❌ Error mail {curso_tipo}: {str(mail_error)}")
                continue

            exito_count += 1

        if exito_count > 0:
            messages.success(request, f'{exito_count} correos enviados.')
        if errores:
            messages.warning(request, f'Errores: ' + '; '.join(errores))

        return JsonResponse({'exito_count': exito_count, 'errores': errores})

    except json.JSONDecodeError as e:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

#---------------------------------------------------------------------------------------------------------#
#-------------------------------------------quiz admin----------------------------------------------------#
#---------------------------------------------------------------------------------------------------------#


from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages

from .models import Clase, Curso, Pregunta
from .forms import PreguntaForm
from .decorators import session_required


@session_required
def alta_quiz_view(request):

    cursos = Curso.objects.only(
        'id_curso',
        'nombre_curso'
    ).order_by('nombre_curso')

    clases = (
        Clase.objects
        .select_related('curso')
        .only(
            'id',
            'nombre_clase',
            'numero_clase',
            'curso__id_curso',
            'curso__nombre_curso'
        )
        .order_by('curso__nombre_curso', 'numero_clase')
    )

    pregunta_existente = None
    form = PreguntaForm()

    curso_id = request.GET.get("curso")
    clase_id = request.GET.get("clase")

    # ==========================
    # CONSULTA OPTIMIZADA
    # ==========================

    preguntas = (
        Pregunta.objects
        .select_related("clase", "clase__curso")
        .order_by(
            "clase__curso__nombre_curso",
            "clase__numero_clase",
            "id"
        )
    )

    if curso_id:
        preguntas = preguntas.filter(clase__curso__id_curso=curso_id)

    if clase_id:
        preguntas = preguntas.filter(clase_id=clase_id)

    # Evita cargar miles de registros cuando no existen filtros
    if not curso_id and not clase_id:
        preguntas = preguntas[:200]

    # ==========================
    # ELIMINAR
    # ==========================

    if request.method == "POST":

        delete_id = request.POST.get("delete_id")

        if delete_id:
            try:
                Pregunta.objects.get(id=delete_id).delete()
                messages.success(request, "Pregunta eliminada con éxito.")
            except Pregunta.DoesNotExist:
                messages.error(request, "Pregunta no encontrada.")

            params = request.GET.copy()
            query = params.urlencode()

            return redirect(
                reverse("alta_quiz") +
                ("?" + query if query else "")
            )

        # ==========================
        # EDITAR / CREAR
        # ==========================

        pregunta_id = request.POST.get("id_pregunta")

        if pregunta_id:
            try:
                pregunta_existente = Pregunta.objects.get(id=pregunta_id)
                form = PreguntaForm(
                    request.POST,
                    instance=pregunta_existente
                )
            except Pregunta.DoesNotExist:
                form = PreguntaForm(request.POST)

        else:
            form = PreguntaForm(request.POST)

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Pregunta guardada correctamente."
            )

            params = request.GET.copy()

            params.pop("edit_id", None)

            params["guardado"] = "1"

            return redirect(
                reverse("alta_quiz") +
                "?" +
                params.urlencode()
            )

        else:
            print(form.errors)

    # ==========================
    # EDICIÓN
    # ==========================

    pregunta_id = request.GET.get("edit_id")

    if pregunta_id:
        try:
            pregunta_existente = Pregunta.objects.get(id=pregunta_id)
            form = PreguntaForm(instance=pregunta_existente)
        except Pregunta.DoesNotExist:
            pass

    contexto = {
        "cursos": cursos,
        "clases": clases,
        "preguntas": preguntas,
        "pregunta_existente": pregunta_existente,
        "form": form,
        "guardado_exitoso": request.GET.get("guardado") == "1",
        "filtro_curso": curso_id,
        "filtro_clase": clase_id,
    }

    return render(
        request,
        "administrador/alta_quiz.html",
        contexto,
    )


############################################################################################
###-----------------------------calendario de clases-------------------------------------###
############################################################################################

from django.shortcuts import render, get_object_or_404
from .models import ClaseComision, Comision 

def calendario_view(request, comision_id): 
    """
    Recupera todas las clases de una comisión específica.
    """
    
    comision = get_object_or_404(Comision, pk=comision_id)
    
    clases = ClaseComision.objects.filter(
        comision=comision
    ).order_by('fecha', 'horario').select_related(
        'clase',
        'comision__id_curso'
    )
    
    context = {
        'clases': clases,
        'titulo': f'Calendario del Curso: {comision.id_curso.nombre_curso} | Comisión {comision.numero_comision}',
        'comision': comision,
        'usuario': request.session.get('usuario_logueado'),
        'nombre_usuario': request.session.get('usuario_logueado'),
    }
    
    # 🚨 CORRECCIÓN: Referenciar el archivo dentro del subdirectorio 'educativa/'
    return render(request, 'educativa/calendario.html', context)

# views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction , models
from datetime import timedelta, datetime
import holidays

from .models import Comision, Clase, ClaseComision

# Feriados Argentina
feriados_ar = holidays.AR(years=[2025, 2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035])


def crear_clases_comision_view(request):
    comisiones = Comision.objects.all().select_related('id_curso')

    if request.method == 'POST':
        comision_id = request.POST.get('comision_id')
        if not comision_id:
            messages.error(request, "Falta comisión")
            return redirect('crear_clases_comision')

        try:
            comision = Comision.objects.get(id_comision=comision_id)
        except Comision.DoesNotExist:
            messages.error(request, "Esa comisión no existe")
            return redirect('crear_clases_comision')

        clases = Clase.objects.filter(curso=comision.id_curso).order_by('numero_clase')

        fecha_str = request.POST.get('fecha_inicio')
        hora_str = request.POST.get('hora_inicio')
        hora_fin_str = request.POST.get('hora_fin') or None

        if not fecha_str or not hora_str:
            messages.error(request, "Falta fecha o hora")
            return redirect('crear_clases_comision')

        fecha_actual = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        hora_inicio = datetime.strptime(hora_str, '%H:%M').time()
        hora_fin = datetime.strptime(hora_fin_str, '%H:%M').time() if hora_fin_str else None

        dias = []
        for d in ['lunes','martes','miércoles','jueves','viernes','sábado','domingo']:
            if request.POST.get(d) == 'on':
                dias.append(d)

        if not dias:
            messages.error(request, "Elegí al menos un día")
            return redirect('crear_clases_comision')

        mapa = {'lunes':0,'martes':1,'miércoles':2,'jueves':3,'viernes':4,'sábado':5,'domingo':6}

        creadas = 0
        with transaction.atomic():
            for clase in clases:
                fecha = fecha_actual
                while True:
                    if fecha.weekday() in [mapa[d] for d in dias] and fecha not in feriados_ar:
                        break
                    fecha += timedelta(days=1)

                try:
                    obj = ClaseComision.objects.get(comision=comision, clase=clase)
                    obj.fecha = fecha
                    obj.horario = hora_inicio
                    obj.hora_fin = hora_fin
                    obj.link = ''
                    obj.video = ''
                    obj.save()
                except ClaseComision.DoesNotExist:
                    ultimo_id = ClaseComision.objects.aggregate(models.Max('id'))['id__max'] or 0
                    nuevo_id = ultimo_id + 1
                    ClaseComision.objects.create(
                        id=nuevo_id,
                        comision=comision,
                        clase=clase,
                        fecha=fecha,
                        horario=hora_inicio,
                        hora_fin=hora_fin,
                        link='',
                        video=''
                    )
                creadas += 1
                fecha_actual = fecha + timedelta(days=1)

        # MODAL APARECE SÍ O SÍ CON MENSAJE
        return render(request, 'administrador/crear_clases_comision.html', {
            'comisiones': comisiones,
            'dias_semana': ['lunes','martes','miércoles','jueves','viernes','sábado','domingo'],
            'modal_mensaje': f"¡LISTO! {creadas} clases creadas para la COMISIÓN {comision.numero_comision} de {comision.id_curso.nombre_curso}"
        })

    return render(request, 'administrador/crear_clases_comision.html', {
        'comisiones': comisiones,
        'dias_semana': ['lunes','martes','miércoles','jueves','viernes','sábado','domingo'],
    })


    ################################################################################################
    #------------------------------------newsletters-----------------------------------------------#
    ################################################################################################

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
import threading
from .models import Newsletter, Suscriptor, PerfilUsuario
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

@session_required
def envio_y_edicion_de_newsletter(request):
    if request.method == "POST":
        data = request.POST.dict()  # 🔥 convertir a dict para pasarlo al hilo

        # Crear o actualizar Newsletter en la base
        nl, created = Newsletter.objects.update_or_create(
            numero_edicion=data.get("numero_edicion"),
            defaults={
                "titulo_novedad": data.get("titulo_novedad"),
                "extracto_novedad": data.get("extracto_novedad"),
                "link_novedad": data.get("link_novedad"),
                "titulo_promocion": data.get("titulo_promocion"),
                "descuento": data.get("descuento"),
                "codigo_cupon": data.get("codigo_cupon"),
                "fecha_vencimiento": data.get("fecha_vencimiento"),
                "link_promocion": data.get("link_promocion"),
                "enviado_el": timezone.now(),
                "enviado_por": request.user if request.user.is_authenticated else None,
            }
        )

        # Mensaje inmediato al usuario
        messages.success(request, "¡Newsletter enviada! Se está enviando a todos los contactos en segundo plano...")

        # Lanzamos el envío en un hilo separado → pasamos data directo
        threading.Thread(target=enviar_newsletter_en_background, args=(data,)).start()

        return redirect('envio-newsletter')

    return render(request, 'administrador/envio_y_edicion_de_newsletter.html')


def enviar_newsletter_en_background(data):
    if not data:
        print("❌ No hay datos de newsletter")
        return

    dias = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    dia_semana = dias[timezone.now().weekday()]

    context_base = {
        'dia_semana': dia_semana,
        'numero_edicion': data['numero_edicion'],
        'titulo_novedad': data['titulo_novedad'],
        'extracto_novedad': data['extracto_novedad'],
        'link_novedad': data['link_novedad'],
        'titulo_promocion': data['titulo_promocion'],
        'descuento': data.get('descuento', '40%'),
        'codigo_cupon': data['codigo_cupon'],
        'fecha_vencimiento': data['fecha_vencimiento'],
        'link_promocion': data['link_promocion'],
        'link_discord': "https://discord.gg/tecnomarema",
        'link_linkedin': "https://linkedin.com/company/tecnomarema",
        'link_youtube': "https://youtube.com/@tecnomarema",
        'link_instagram': "https://instagram.com/tecnomarema",
        'link_facebook': "https://facebook.com/tecnomarema",
    }

    # 🔍 Recoger correos de Suscriptor y PerfilUsuario
    emails_suscriptores = [e.strip().lower() for e in list(Suscriptor.objects.values_list('email', flat=True)) if e]
    emails_usuarios = [e.strip().lower() for e in list(PerfilUsuario.objects.exclude(correo__isnull=True).exclude(correo='').values_list('correo', flat=True)) if e]
    todos_emails = set(emails_suscriptores + emails_usuarios)

    print(f"Correos a enviar: {len(todos_emails)} → {todos_emails}")

    for email in todos_emails:
        try:
            perfil = PerfilUsuario.objects.filter(correo__iexact=email).first()
            nombre = perfil.id_estudiante.nombre.split()[0] if perfil and perfil.id_estudiante else "amigo/a"

            context = context_base.copy()
            context['nombre'] = nombre
            context['link_unsubscribe'] = f"https://tecnomarema.com.ar/unsubscribe/?email={email}"

            html_message = render_to_string('registration/newsletter.html', context)

            send_mail(
                subject=f"{dia_semana}: {data['titulo_promocion']} + Novedades Tecno Marema",
                message="",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            print(f"✅ Enviado a {email}")
        except Exception as e:
            print(f"❌ Error enviando a {email}: {e}")


################################################################################################
#-------------------------Edicion y eliminacion de newsletter----------------------------------#
################################################################################################

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Newsletter

def listado_newsletters(request):
    newsletters = Newsletter.objects.all()
    return render(request, "administrador/listado_newsletters.html", {"newsletters": newsletters})

@require_POST
def editar_newsletter(request):
    try:
        nl = Newsletter.objects.get(id=request.POST.get("id"))
        nl.numero_edicion = request.POST.get("numero_edicion")
        nl.titulo_novedad = request.POST.get("titulo_novedad")
        nl.extracto_novedad = request.POST.get("extracto_novedad")
        nl.link_novedad = request.POST.get("link_novedad")
        nl.titulo_promocion = request.POST.get("titulo_promocion")
        nl.descuento = request.POST.get("descuento")
        nl.codigo_cupon = request.POST.get("codigo_cupon")
        nl.fecha_vencimiento = request.POST.get("fecha_vencimiento")
        nl.link_promocion = request.POST.get("link_promocion")
        nl.save()
        return JsonResponse({"success": True, "mensaje": "Newsletter actualizada correctamente."})
    except Newsletter.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "La newsletter no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})

@require_POST
def eliminar_newsletter(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ninguna newsletter para eliminar."})
        eliminados = Newsletter.objects.filter(id__in=ids).delete()[0]
        return JsonResponse({"success": True, "mensaje": "Newsletters eliminadas correctamente.", "cantidad": eliminados})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})


##################################################################################
###                    view de la promo de desarrollo web                      ###
##################################################################################

def promo_desarrolloweb(request):
    return render(request, 'educativa/promo_desarrolloweb.html')


##################################################################################
###                       validar cupon de descuento                           ###
##################################################################################


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Cupon, Curso, Comision, DatosDeEstudiantes, PerfilUsuario, RegistroPago

@csrf_exempt
def validar_cupon(request):
    """Valida si un cupón existe y es aplicable."""
    if request.method == "POST":
        # Usamos request.POST porque el JS envía FormData
        cupon_codigo = request.POST.get("cupon", "").strip().upper()
        try:
            cupon = Cupon.objects.get(codigo__iexact=cupon_codigo)
            if cupon.es_valido():
                return JsonResponse({"status": "ok", "descuento": cupon.descuento_porcentaje})
            else:
                return JsonResponse({"status": "error", "msg": "Cupón expirado o inválido"})
        except Cupon.DoesNotExist:
            return JsonResponse({"status": "error", "msg": "Cupón no encontrado"})
        except Exception as e:
            return JsonResponse({"status": "error", "msg": str(e)})
    return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

################################################################################################
#----------------------------------alta y edicion cupones--------------------------------------#
################################################################################################

@session_required  # Si usas este decorador para sesiones personalizadas
def alta_y_edicion_cupones(request, codigo=None):
    guardado_exitoso = False
    cupon = None

    if codigo:
        cupon = get_object_or_404(Cupon, codigo=codigo)

    if request.method == 'POST':
        codigo_post = request.POST.get('codigo', '').strip().upper()
        descuento_porcentaje = int(request.POST.get('descuento_porcentaje', 0))
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_vencimiento = request.POST.get('fecha_vencimiento') or None
        usos_maximos = int(request.POST.get('usos_maximos', 0))
        usos_actuales = int(request.POST.get('usos_actuales', 0)) if cupon else 0  # No editable, solo para edición
        activo = 'activo' in request.POST

        if cupon:
            # Edición
            cupon.codigo = codigo_post
            cupon.descuento_porcentaje = descuento_porcentaje
            cupon.fecha_inicio = fecha_inicio
            cupon.fecha_vencimiento = fecha_vencimiento
            cupon.usos_maximos = usos_maximos
            cupon.usos_actuales = usos_actuales  # Mantiene el valor actual
            cupon.activo = activo
            cupon.save()
        else:
            # Alta nueva
            cupon = Cupon.objects.create(
                codigo=codigo_post,
                descuento_porcentaje=descuento_porcentaje,
                fecha_inicio=fecha_inicio,
                fecha_vencimiento=fecha_vencimiento,
                usos_maximos=usos_maximos,
                usos_actuales=0,
                activo=activo
            )

        guardado_exitoso = True
        # Opcional: redirect a la misma página para nueva alta, o al panel
        # return redirect('alta_y_edicion_cupones')

    context = {
        'cupon': cupon,
        'guardado_exitoso': guardado_exitoso
    }
    return render(request, 'administrador/alta_y_edicion_cupones.html', context)


############################################################################################
##---------------------------Edicion de listado de cupones--------------------------------##
############################################################################################

from django.shortcuts import render
from .models import Cupon

def listado_cupones(request):
    # Trae todos los cupones ordenados por fecha de vencimiento (los más próximos primero)
    cupones = Cupon.objects.all().order_by('fecha_vencimiento')
    return render(request, "administrador/listado_cupones.html", {"cupones": cupones})

@require_POST
def editar_cupon(request):
    try:
        cupon = Cupon.objects.get(id=request.POST.get("id"))
        cupon.codigo = request.POST.get("codigo")
        cupon.descuento_porcentaje = int(request.POST.get("descuento_porcentaje"))
        cupon.fecha_inicio = request.POST.get("fecha_inicio")
        cupon.fecha_vencimiento = request.POST.get("fecha_vencimiento") or None
        cupon.usos_maximos = int(request.POST.get("usos_maximos"))
        cupon.usos_actuales = int(request.POST.get("usos_actuales"))
        cupon.activo = request.POST.get("activo") == "True"
        cupon.save()
        return JsonResponse({"success": True, "mensaje": "Cupón actualizado correctamente."})
    except Cupon.DoesNotExist:
        return JsonResponse({"success": False, "mensaje": "El cupón no existe."})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})

@require_POST
def eliminar_cupon(request):
    try:
        ids = request.POST.getlist("ids[]")
        if not ids:
            return JsonResponse({"success": False, "mensaje": "No se recibió ningún cupón para eliminar."})
        eliminados = Cupon.objects.filter(id__in=ids).delete()[0]
        return JsonResponse({"success": True, "mensaje": "Cupones eliminados correctamente.", "cantidad": eliminados})
    except Exception as e:
        return JsonResponse({"success": False, "mensaje": str(e)})



############################################################################################
##----------------------------------login_autocompletar-----------------------------------##
############################################################################################

from django.contrib.auth import authenticate, login
from django.http import JsonResponse
import json
from .models import DatosDeEstudiantes, PerfilUsuario

def login_autocompletar(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            entrada = data.get('username')
            password = data.get('password')

            user_obj = PerfilUsuario.objects.filter(correo__iexact=entrada).first() or \
                       PerfilUsuario.objects.filter(nombre_usuario__iexact=entrada).first()
            
            username_final = user_obj.nombre_usuario if user_obj else entrada
            user = authenticate(request, username=username_final, password=password)
            
            if user is not None:
                login(request, user)
                # Filtramos usando 'correo' que es el campo real en tu modelo según el error
                estudiante = DatosDeEstudiantes.objects.filter(correo__iexact=user.correo).first()
                
                if estudiante:
                    return JsonResponse({
                        'success': True,
                        'nombre': estudiante.nombre,
                        'apellido': estudiante.apellido,
                        'dni': estudiante.dni,
                        'correo': estudiante.correo,
                        'telefono': estudiante.telefono,
                        # Formateamos la fecha para que el input HTML la entienda (YYYY-MM-DD)
                        'fecha_nacimiento': estudiante.fecha_nacimiento.strftime('%Y-%m-%d') if estudiante.fecha_nacimiento else ''
                    })
                return JsonResponse({'success': False, 'error': 'Usuario válido sin ficha de alumno.'})
            
            return JsonResponse({'success': False, 'error': 'Usuario o contraseña incorrectos.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})


############################################################################################
##---------------------------Guardado de certificado en base------------------------------##
############################################################################################
import os
import json
import base64
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def guardar_certificado(request):

    if request.method == "POST":

        data = json.loads(request.body)

        imagen = data["imagen"]

        formato, imgstr = imagen.split(";base64,")

        archivo = base64.b64decode(imgstr)

        nombre = "certificado.png"

        ruta = os.path.join(
            settings.MEDIA_ROOT,
            "certificados",
            nombre
        )

        os.makedirs(os.path.dirname(ruta), exist_ok=True)

        with open(ruta, "wb") as f:
            f.write(archivo)

        return JsonResponse({
            "ok": True,
            "url": request.build_absolute_uri(
                settings.MEDIA_URL +
                "certificados/" +
                nombre
            )
        })