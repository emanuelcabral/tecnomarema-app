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

def home(request):
    return render(request, 'educativa/home.html')

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
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import DatosDeEstudiantes, PerfilUsuario, Comision, RegistroPago, Curso


# @csrf_exempt
# def guardar_datos_inscripcion_paga(request):
#     if request.method == "POST":
#         sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
#         try:
#             # ============================
#             # 🔹 Datos del formulario
#             # ============================
#             nombre = request.POST.get("nombre")
#             apellido = request.POST.get("apellido")
#             documento = request.POST.get("documento")
#             email = request.POST.get("email")
#             fecha_nacimiento = request.POST.get("fecha_nacimiento")
#             pais = request.POST.get("pais")
#             provincia = request.POST.get("provincia")
#             telefono = request.POST.get("telefono")
#             genero = request.POST.get("genero")
#             curso_id = request.POST.get("curso")
#             medio_pago = request.POST.get("medio_pago")
#             comision_nombre = request.POST.get("comision")
#             comprobante = request.FILES.get("comprobante")

#             print("Datos recibidos:", nombre, apellido, documento, email, curso_id)

#             # ============================
#             # 🔹 Validaciones
#             # ============================
#             if DatosDeEstudiantes.objects.filter(dni=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este DNI."}, status=400)

#             if DatosDeEstudiantes.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este correo."}, status=400)

#             if PerfilUsuario.objects.filter(nombre_usuario=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Este DNI ya está registrado como usuario."}, status=400)

#             if PerfilUsuario.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Este correo ya está registrado como usuario."}, status=400)

#             # if not comprobante:
#             #     return JsonResponse({"status": "error", "msg": "No se recibió comprobante"}, status=400)

#             # Validar comprobante SOLO si el medio de pago es transferencia
#             if medio_pago == "transferencia_bancaria":
#                 if not comprobante:
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": "Falta comprobante. Por favor, adjuntá el comprobante de pago para continuar."
#                     }, status=400)


#             # ============================
#             # 🔹 Curso y comisión
#             # ============================
#             curso_obj = Curso.objects.filter(id_curso=curso_id).first()
#             if not curso_obj:
#                 return JsonResponse({"status": "error", "msg": f"No se encontró el curso con ID {curso_id}"}, status=400)
#             curso_nombre = curso_obj.nombre_curso

#             comision = Comision.objects.filter(numero_comision=comision_nombre, id_curso=curso_obj).first()
#             if not comision:
#                 return JsonResponse({"status": "error", "msg": f"No se encontró la comisión '{comision_nombre}' para el curso {curso_nombre}"}, status=400)

#             # ============================
#             # 🔹 Crear estudiante
#             # ============================
#             ultimo = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
#             nuevo_id = str(int(ultimo.id_estudiante) + 1 if ultimo else 1).zfill(6)

#             estudiante = DatosDeEstudiantes.objects.create(
#                 id_estudiante=nuevo_id,
#                 nombre=nombre,
#                 apellido=apellido,
#                 dni=documento,
#                 correo=email,
#                 fecha_nacimiento=fecha_nacimiento,
#                 pais=pais,
#                 provincia=provincia,
#                 telefono=telefono,
#                 genero=genero
#             )

#             # Asignar comisión al primer campo disponible
#             asignado = False
#             for i in range(1, 10):
#                 campo = f'cursando{i}'
#                 if getattr(estudiante, campo) is None:
#                     setattr(estudiante, campo, comision)
#                     estudiante.save()
#                     asignado = True
#                     break
#             if not asignado:
#                 return JsonResponse({"status": "error", "msg": "El estudiante ya está inscrito en el máximo de comisiones."}, status=400)

#             # ============================
#             # 🔹 Crear usuario vinculado
#             # ============================
#             usuario_id = str(int(PerfilUsuario.objects.order_by('-id_usuario').first().id_usuario) + 1 if PerfilUsuario.objects.exists() else 1).zfill(6)

#             usuario = PerfilUsuario.objects.create(
#                 id_usuario=usuario_id,
#                 id_estudiante=estudiante,
#                 nombre_usuario=documento,
#                 correo=email,
#                 rol="alumno",
#                 is_active=True
#             )
#             usuario.set_password("pass1234")
#             usuario.save()

#             # ============================
#             # 🔹 Registrar pago
#             # ============================
#             RegistroPago.objects.create(
#                 estudiante=estudiante,
#                 comision=comision,
#                 plataforma="web",
#                 medio_pago=medio_pago,
#                 estado_pago="Verificando",
#                 monto=0,
#                 fecha_pago=timezone.now(),
#                 id_transaccion="",
#                 archivo_comprobante=comprobante
#             )

#             # ============================
#             # 💌 Correo interno (registro_pago.html)
#             # ============================
#             context_interno = {
#                 "nombre": nombre,
#                 "apellido": apellido,
#                 "email": email,
#                 "documento": documento,
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "pais": pais,
#                 "provincia": provincia,
#                 "telefono": telefono,
#                 "medio_pago": medio_pago,
#                 "fecha": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
#             }
#             html_interno = render_to_string("registration/registro_pago.html", context_interno)
#             text_interno = strip_tags(html_interno)

#             email_interno = EmailMultiAlternatives(
#                 subject="📥 Nuevo alumno inscripto y compra registrada",
#                 body=text_interno,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=["tecnomarema.ar@gmail.com"],
#             )
#             email_interno.attach_alternative(html_interno, "text/html")
#             email_interno.send()

#             # ============================
#             # 💌 Correo alumno (bienvenida_paga.html)
#             # ============================
#             context_bienvenida = {
#                 "nombre": f"{nombre} {apellido}",
#                 "usuario": documento,
#                 "password": "pass1234",
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "reset_url": "https://tecnomarema.com/reset-password",  # ⚠️ ajustar
#             }
#             html_bienvenida = render_to_string("registration/bienvenida_paga.html", context_bienvenida)
#             text_bienvenida = strip_tags(html_bienvenida)

#             email_alumno = EmailMultiAlternatives(
#                 subject="🎓 Bienvenido/a a tu curso en Tecno Marema",
#                 body=text_bienvenida,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=[email],
#             )
#             email_alumno.attach_alternative(html_bienvenida, "text/html")
#             email_alumno.send()

#             # ============================
#             return JsonResponse({"status": "ok", "id_estudiante": nuevo_id, "id_usuario": usuario_id})

#         except Exception as e:
#             print("ERROR EN INSCRIPCION:", e)
#             return JsonResponse({"status": "error", "msg": str(e)}, status=500)

#     return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

#------------------------------------------------------------------------------------------------------

# @csrf_exempt
# def guardar_datos_inscripcion_paga(request):
#     if request.method == "POST":
#         sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
#         try:
#             # ============================
#             # 🔹 Datos del formulario
#             # ============================
#             nombre = request.POST.get("nombre")
#             apellido = request.POST.get("apellido")
#             documento = request.POST.get("documento")
#             email = request.POST.get("email")
#             fecha_nacimiento = request.POST.get("fecha_nacimiento")
#             pais = request.POST.get("pais")
#             provincia = request.POST.get("provincia")
#             telefono = request.POST.get("telefono")
#             genero = request.POST.get("genero")
#             curso_id = request.POST.get("curso")
#             medio_pago = request.POST.get("medio_pago")
#             comision_nombre = request.POST.get("comision")
#             comprobante = request.FILES.get("comprobante")

#             print("Datos recibidos:", nombre, apellido, documento, email, curso_id)

#             # ============================
#             # 🔹 Validaciones básicas
#             # ============================
#             campos_obligatorios = {
#                 "nombre": nombre,
#                 "apellido": apellido,
#                 "documento": documento,
#                 "email": email,
#                 "fecha_nacimiento": fecha_nacimiento,
#                 "pais": pais,
#                 "provincia": provincia,
#                 "telefono": telefono,
#                 "curso": curso_id,
#                 "comision": comision_nombre,
#                 "medio_pago": medio_pago,
#             }

#             faltantes = [campo for campo, valor in campos_obligatorios.items() if not valor]
#             if faltantes:
#                 return JsonResponse({
#                     "status": "error",
#                     "msg": f"Faltan completar los siguientes campos: {', '.join(faltantes)}"
#                 }, status=400)

#             # Validar comprobante SOLO si el medio de pago es transferencia
#             if medio_pago == "transferencia_bancaria":
#                 if not comprobante:
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": "Falta comprobante. Por favor, adjuntá el comprobante de pago para continuar."
#                     }, status=400)

#             # ============================
#             # 🔹 Validaciones de duplicados
#             # ============================
#             if DatosDeEstudiantes.objects.filter(dni=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este DNI."}, status=400)

#             if DatosDeEstudiantes.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este correo."}, status=400)

#             if PerfilUsuario.objects.filter(nombre_usuario=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Este DNI ya está registrado como usuario."}, status=400)

#             if PerfilUsuario.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Este correo ya está registrado como usuario."}, status=400)

#             # ============================
#             # 🔹 Curso y comisión
#             # ============================
#             curso_obj = Curso.objects.filter(id_curso=curso_id).first()
#             if not curso_obj:
#                 return JsonResponse({"status": "error", "msg": f"No se encontró el curso con ID {curso_id}"}, status=400)
#             curso_nombre = curso_obj.nombre_curso

#             comision = Comision.objects.filter(numero_comision=comision_nombre, id_curso=curso_obj).first()
#             if not comision:
#                 return JsonResponse({"status": "error", "msg": f"No se encontró la comisión '{comision_nombre}' para el curso {curso_nombre}"}, status=400)

#             # ============================
#             # 🔹 Crear estudiante
#             # ============================
#             ultimo = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
#             nuevo_id = str(int(ultimo.id_estudiante) + 1 if ultimo else 1).zfill(6)

#             estudiante = DatosDeEstudiantes.objects.create(
#                 id_estudiante=nuevo_id,
#                 nombre=nombre,
#                 apellido=apellido,
#                 dni=documento,
#                 correo=email,
#                 fecha_nacimiento=fecha_nacimiento,
#                 pais=pais,
#                 provincia=provincia,
#                 telefono=telefono,
#                 genero=genero
#             )

#             # Asignar comisión al primer campo disponible
#             asignado = False
#             for i in range(1, 10):
#                 campo = f'cursando{i}'
#                 if getattr(estudiante, campo) is None:
#                     setattr(estudiante, campo, comision)
#                     estudiante.save()
#                     asignado = True
#                     break
#             if not asignado:
#                 return JsonResponse({"status": "error", "msg": "El estudiante ya está inscrito en el máximo de comisiones."}, status=400)

#             # ============================
#             # 🔹 Crear usuario vinculado
#             # ============================
#             usuario_id = str(int(PerfilUsuario.objects.order_by('-id_usuario').first().id_usuario) + 1 if PerfilUsuario.objects.exists() else 1).zfill(6)

#             usuario = PerfilUsuario.objects.create(
#                 id_usuario=usuario_id,
#                 id_estudiante=estudiante,
#                 nombre_usuario=documento,
#                 correo=email,
#                 rol="alumno",
#                 is_active=True
#             )
#             usuario.set_password("pass1234")
#             usuario.save()

#             # ============================
#             # 🔹 Registrar pago
#             # ============================
#             RegistroPago.objects.create(
#                 estudiante=estudiante,
#                 comision=comision,
#                 plataforma="web",
#                 medio_pago=medio_pago,
#                 estado_pago="Verificando",
#                 monto=0,
#                 fecha_pago=timezone.now(),
#                 id_transaccion="",
#                 archivo_comprobante=comprobante
#             )

#             # ============================
#             # 💌 Correo interno (registro_pago.html)
#             # ============================
#             context_interno = {
#                 "nombre": nombre,
#                 "apellido": apellido,
#                 "email": email,
#                 "documento": documento,
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "pais": pais,
#                 "provincia": provincia,
#                 "telefono": telefono,
#                 "medio_pago": medio_pago,
#                 "fecha": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
#             }
#             html_interno = render_to_string("registration/registro_pago.html", context_interno)
#             text_interno = strip_tags(html_interno)

#             email_interno = EmailMultiAlternatives(
#                 subject="📥 Nuevo alumno inscripto y compra registrada",
#                 body=text_interno,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=["tecnomarema.ar@gmail.com"],
#             )
#             email_interno.attach_alternative(html_interno, "text/html")
#             email_interno.send()

#             # ============================
#             # 💌 Correo alumno (bienvenida_paga.html)
#             # ============================
#             context_bienvenida = {
#                 "nombre": f"{nombre} {apellido}",
#                 "usuario": documento,
#                 "password": "pass1234",
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "reset_url": "https://tecnomarema.com/reset-password",  # ⚠️ ajustar
#             }
#             html_bienvenida = render_to_string("registration/bienvenida_paga.html", context_bienvenida)
#             text_bienvenida = strip_tags(html_bienvenida)

#             email_alumno = EmailMultiAlternatives(
#                 subject="🎓 Bienvenido/a a tu curso en Tecno Marema",
#                 body=text_bienvenida,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=[email],
#             )
#             email_alumno.attach_alternative(html_bienvenida, "text/html")
#             email_alumno.send()

#             # ============================
#             # 🔹 Respuesta final
#             # ============================
#             return JsonResponse({"status": "ok", "id_estudiante": nuevo_id, "id_usuario": usuario_id})

#         except Exception as e:
#             print("ERROR EN INSCRIPCION:", e)
#             return JsonResponse({"status": "error", "msg": str(e)}, status=500)

#     return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

#---------------------------------------------------------------------------------------------------------------------------------

# @csrf_exempt
# def guardar_datos_inscripcion_paga(request):
#     if request.method == "POST":
#         sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

#         try:
#             # ============================
#             # 🔹 Datos del formulario
#             # ============================
#             nombre = request.POST.get("nombre")
#             apellido = request.POST.get("apellido")
#             documento = request.POST.get("documento")
#             email = request.POST.get("email")
#             fecha_nacimiento = request.POST.get("fecha_nacimiento")
#             pais = request.POST.get("pais")
#             provincia = request.POST.get("provincia")
#             telefono = request.POST.get("telefono")
#             genero = request.POST.get("genero")
#             curso_id = request.POST.get("curso")
#             medio_pago = request.POST.get("medio_pago")
#             comision_nombre = request.POST.get("comision")
#             comprobante = request.FILES.get("comprobante")

#             # Datos de pago con MercadoPago (token + método)
#             token = request.POST.get("token")
#             payment_method_id = request.POST.get("payment_method_id")

#             print("📥 Datos recibidos:", nombre, apellido, documento, email, curso_id, medio_pago)

#             # ============================
#             # 🔹 Validaciones básicas
#             # ============================
#             campos_obligatorios = {
#                 "nombre": nombre,
#                 "apellido": apellido,
#                 "documento": documento,
#                 "email": email,
#                 "fecha_nacimiento": fecha_nacimiento,
#                 "pais": pais,
#                 "provincia": provincia,
#                 "telefono": telefono,
#                 "curso": curso_id,
#                 "comision": comision_nombre,
#                 "medio_pago": medio_pago,
#             }

#             faltantes = [campo for campo, valor in campos_obligatorios.items() if not valor]
#             if faltantes:
#                 return JsonResponse({
#                     "status": "error",
#                     "msg": f"Faltan completar los siguientes campos: {', '.join(faltantes)}"
#                 }, status=400)

#             # ============================
#             # 🔹 Validar comprobante o token según medio de pago
#             # ============================
#             if medio_pago == "transferencia_bancaria":
#                 if not comprobante:
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": "Falta comprobante. Por favor, adjuntá el comprobante de pago para continuar."
#                     }, status=400)

#             elif medio_pago in ["debito", "credito_1", "credito_cuotas"]:
#                 if not token or not payment_method_id:
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": "No se recibió el token de MercadoPago. Por favor, intentá nuevamente."
#                     }, status=400)

#                 # ============================
#                 # 🔹 Validar con MercadoPago
#                 # ============================
#                 payment_data = {
#                     "transaction_amount": float(getattr(settings, "MP_MONTO_CURSO", 10000)),
#                     "token": token,
#                     "description": f"Inscripción curso {curso_id} - comisión {comision_nombre}",
#                     "installments": 1 if medio_pago != "credito_cuotas" else 3,
#                     "payment_method_id": payment_method_id,
#                     "payer": {"email": email},
#                 }

#                 result = sdk.payment().create(payment_data)
#                 payment = result.get("response", {})

#                 if payment.get("status") != "approved":
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": f"Pago rechazado: {payment.get('status_detail', 'motivo desconocido')}."
#                     }, status=400)

#                 print("✅ Pago aprobado por MercadoPago:", payment.get("id"))

#             # ============================
#             # 🔹 Validaciones de duplicados
#             # ============================
#             if DatosDeEstudiantes.objects.filter(dni=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este DNI."}, status=400)

#             if DatosDeEstudiantes.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este correo."}, status=400)

#             if PerfilUsuario.objects.filter(nombre_usuario=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Este DNI ya está registrado como usuario."}, status=400)

#             if PerfilUsuario.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Este correo ya está registrado como usuario."}, status=400)

#             # ============================
#             # 🔹 Curso y comisión
#             # ============================
#             curso_obj = Curso.objects.filter(id_curso=curso_id).first()
#             if not curso_obj:
#                 return JsonResponse({"status": "error", "msg": f"No se encontró el curso con ID {curso_id}"}, status=400)
#             curso_nombre = curso_obj.nombre_curso

#             comision = Comision.objects.filter(numero_comision=comision_nombre, id_curso=curso_obj).first()
#             if not comision:
#                 return JsonResponse({"status": "error", "msg": f"No se encontró la comisión '{comision_nombre}' para el curso {curso_nombre}"}, status=400)

#             # ============================
#             # 🔹 Crear estudiante
#             # ============================
#             ultimo = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
#             nuevo_id = str(int(ultimo.id_estudiante) + 1 if ultimo else 1).zfill(6)

#             estudiante = DatosDeEstudiantes.objects.create(
#                 id_estudiante=nuevo_id,
#                 nombre=nombre,
#                 apellido=apellido,
#                 dni=documento,
#                 correo=email,
#                 fecha_nacimiento=fecha_nacimiento,
#                 pais=pais,
#                 provincia=provincia,
#                 telefono=telefono,
#                 genero=genero
#             )

#             # Asignar comisión al primer campo libre
#             asignado = False
#             for i in range(1, 10):
#                 campo = f'cursando{i}'
#                 if getattr(estudiante, campo) is None:
#                     setattr(estudiante, campo, comision)
#                     estudiante.save()
#                     asignado = True
#                     break
#             if not asignado:
#                 return JsonResponse({"status": "error", "msg": "El estudiante ya está inscrito en el máximo de comisiones."}, status=400)

#             # ============================
#             # 🔹 Crear usuario vinculado
#             # ============================
#             ultimo_usuario = PerfilUsuario.objects.order_by('-id_usuario').first()
#             usuario_id = str(int(ultimo_usuario.id_usuario) + 1 if ultimo_usuario else 1).zfill(6)

#             usuario = PerfilUsuario.objects.create(
#                 id_usuario=usuario_id,
#                 id_estudiante=estudiante,
#                 nombre_usuario=documento,
#                 correo=email,
#                 rol="alumno",
#                 is_active=True
#             )
#             usuario.set_password("pass1234")
#             usuario.save()

#             # ============================
#             # 🔹 Registrar pago (según medio)
#             # ============================
#             estado_pago = "Pendiente" if medio_pago == "transferencia_bancaria" else "Aprobado"
#             id_transaccion = ""
#             if medio_pago in ["debito", "credito_1", "credito_cuotas"]:
#                 id_transaccion = payment.get("id")

#             RegistroPago.objects.create(
#                 estudiante=estudiante,
#                 comision=comision,
#                 plataforma="web",
#                 medio_pago=medio_pago,
#                 estado_pago=estado_pago,
#                 monto=float(getattr(settings, "MP_MONTO_CURSO", 10000)),
#                 fecha_pago=timezone.now(),
#                 id_transaccion=id_transaccion,
#                 archivo_comprobante=comprobante
#             )

#             # ============================
#             # 💌 Correos (interno + alumno)
#             # ============================
#             context_interno = {
#                 "nombre": nombre,
#                 "apellido": apellido,
#                 "email": email,
#                 "documento": documento,
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "pais": pais,
#                 "provincia": provincia,
#                 "telefono": telefono,
#                 "medio_pago": medio_pago,
#                 "estado_pago": estado_pago,
#                 "fecha": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
#             }
#             html_interno = render_to_string("registration/registro_pago.html", context_interno)
#             text_interno = strip_tags(html_interno)

#             email_interno = EmailMultiAlternatives(
#                 subject="📥 Nuevo alumno inscripto y pago registrado",
#                 body=text_interno,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=["tecnomarema.ar@gmail.com"],
#             )
#             email_interno.attach_alternative(html_interno, "text/html")
#             email_interno.send()

#             # Correo al alumno
#             context_bienvenida = {
#                 "nombre": f"{nombre} {apellido}",
#                 "usuario": documento,
#                 "password": "pass1234",
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "reset_url": "https://tecnomarema.com/reset-password",
#             }
#             html_bienvenida = render_to_string("registration/bienvenida_paga.html", context_bienvenida)
#             text_bienvenida = strip_tags(html_bienvenida)

#             email_alumno = EmailMultiAlternatives(
#                 subject="🎓 Bienvenido/a a tu curso en Tecno Marema",
#                 body=text_bienvenida,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=[email],
#             )
#             email_alumno.attach_alternative(html_bienvenida, "text/html")
#             email_alumno.send()

#             # ============================
#             # 🔹 Respuesta final
#             # ============================
#             return JsonResponse({
#                 "status": "ok",
#                 "id_estudiante": nuevo_id,
#                 "id_usuario": usuario_id,
#                 "estado_pago": estado_pago
#             })

#         except Exception as e:
#             print("❌ ERROR EN INSCRIPCIÓN:", e)
#             return JsonResponse({"status": "error", "msg": str(e)}, status=500)

#     return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)
#------------------------------------------------------------------------------- gemini 17/10 -----------------

# # views.py (ADAPTADO Y COMPLETO)

# from django.views.decorators.csrf import csrf_exempt
# from django.http import JsonResponse
# from django.utils import timezone
# from django.core.mail import EmailMultiAlternatives
# from django.template.loader import render_to_string
# from django.utils.html import strip_tags
# from django.conf import settings
# from .models import DatosDeEstudiantes, PerfilUsuario, Comision, RegistroPago, Curso
# import mercadopago


# @csrf_exempt
# def guardar_datos_inscripcion_paga(request):
#     if request.method == "POST":
#         sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

#         try:
#             # ============================
#             # 🔹 Datos del formulario
#             # ============================
#             nombre = request.POST.get("nombre")
#             apellido = request.POST.get("apellido")
#             documento = request.POST.get("documento")
#             email = request.POST.get("email")
#             fecha_nacimiento = request.POST.get("fecha_nacimiento")
#             pais = request.POST.get("pais")
#             provincia = request.POST.get("provincia")
#             telefono = request.POST.get("telefono")
#             genero = request.POST.get("genero")
#             curso_id = request.POST.get("curso")
#             medio_pago = request.POST.get("medio_pago")
#             comision_nombre = request.POST.get("comision")
#             comprobante = request.FILES.get("comprobante")

#             # Datos de pago MercadoPago (CardForm)
#             token = request.POST.get("token")
#             payment_method_id = request.POST.get("payment_method_id")
#             cuotas = int(request.POST.get("cuotas", 1))

#             print("📥 Datos recibidos:", nombre, apellido, documento, email, curso_id, medio_pago)

#             # ===============================================
#             # 💡 PASO 1: Obtener el Curso y su Precio Dinámico
#             # ===============================================
#             curso_obj = Curso.objects.filter(id_curso=curso_id).first()
#             if not curso_obj:
#                 return JsonResponse({
#                     "status": "error",
#                     "msg": f"No se encontró el curso con ID {curso_id}"
#                 }, status=400)

#             monto_dinamico = float(curso_obj.precio_final)
#             curso_nombre = curso_obj.nombre_curso

#             # ============================
#             # 🔹 Validaciones básicas
#             # ============================
#             campos_obligatorios = {
#                 "nombre": nombre, "apellido": apellido, "documento": documento,
#                 "email": email, "fecha_nacimiento": fecha_nacimiento, "pais": pais,
#                 "provincia": provincia, "telefono": telefono, "curso": curso_id,
#                 "comision": comision_nombre, "medio_pago": medio_pago,
#             }

#             faltantes = [campo for campo, valor in campos_obligatorios.items() if not valor]
#             if faltantes:
#                 return JsonResponse({
#                     "status": "error",
#                     "msg": f"Faltan completar los siguientes campos: {', '.join(faltantes)}"
#                 }, status=400)

#             # ============================
#             # 🔹 Validar comprobante o token según medio
#             # ============================
#             if medio_pago == "transferencia_bancaria":
#                 if not comprobante:
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": "Falta comprobante. Por favor, adjuntá el comprobante de pago."
#                     }, status=400)

#             elif medio_pago in ["debito", "credito_1", "credito_cuotas"]:
#                 if not token or not payment_method_id:
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": "Faltan datos de la tarjeta. Intentá nuevamente."
#                     }, status=400)

#                 # ============================
#                 # 🔹 Validar con MercadoPago (CardForm)
#                 # ============================
#                 payment_data = {
#                     "transaction_amount": monto_dinamico,
#                     "token": token,
#                     "description": f"Inscripción curso {curso_nombre} - comisión {comision_nombre}",
#                     "installments": cuotas if medio_pago == "credito_cuotas" else 1,
#                     "payment_method_id": payment_method_id,
#                     "payer": {"email": email},
#                 }

#                 try:
#                     result = sdk.payment().create(payment_data)
#                     payment = result.get("response", {})
#                 except Exception as e:
#                     print("❌ Error MercadoPago:", e)
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": f"Error comunicándose con MercadoPago: {str(e)}"
#                     }, status=500)

#                 status_mp = payment.get("status", "").lower()
#                 id_transaccion = payment.get("id", "")
#                 detalle_status = payment.get("status_detail", "")

#                 if status_mp != "approved":
#                     # Registrar como rechazado
#                     RegistroPago.objects.create(
#                         estudiante=None,
#                         comision=None,
#                         plataforma="web",
#                         medio_pago=medio_pago,
#                         estado_pago=status_mp,
#                         monto=monto_dinamico,
#                         fecha_pago=timezone.now(),
#                         id_transaccion=id_transaccion
#                     )
#                     return JsonResponse({
#                         "status": "error",
#                         "msg": f"Pago rechazado: {detalle_status or 'motivo desconocido'}."
#                     }, status=400)

#                 print("✅ Pago aprobado por MercadoPago:", id_transaccion)
#                 estado_pago = "Aprobado"

#             else:
#                 estado_pago = "Pendiente"
#                 id_transaccion = ""

#             # ============================
#             # 🔹 Validaciones duplicados
#             # ============================
#             if DatosDeEstudiantes.objects.filter(dni=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este DNI."}, status=400)
#             if DatosDeEstudiantes.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Ya existe un estudiante con este correo."}, status=400)
#             if PerfilUsuario.objects.filter(nombre_usuario=documento).exists():
#                 return JsonResponse({"status": "error", "msg": "Este DNI ya está registrado como usuario."}, status=400)
#             if PerfilUsuario.objects.filter(correo=email).exists():
#                 return JsonResponse({"status": "error", "msg": "Este correo ya está registrado como usuario."}, status=400)

#             # ============================
#             # 🔹 Buscar comisión
#             # ============================
#             comision = Comision.objects.filter(
#                 numero_comision=comision_nombre, id_curso=curso_obj
#             ).first()
#             if not comision:
#                 return JsonResponse({
#                     "status": "error",
#                     "msg": f"No se encontró la comisión '{comision_nombre}' para el curso {curso_nombre}"
#                 }, status=400)

#             # ============================
#             # 🔹 Crear estudiante
#             # ============================
#             ultimo = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
#             nuevo_id = str(int(ultimo.id_estudiante) + 1 if ultimo else 1).zfill(6)

#             estudiante = DatosDeEstudiantes.objects.create(
#                 id_estudiante=nuevo_id,
#                 nombre=nombre,
#                 apellido=apellido,
#                 dni=documento,
#                 correo=email,
#                 fecha_nacimiento=fecha_nacimiento,
#                 pais=pais,
#                 provincia=provincia,
#                 telefono=telefono,
#                 genero=genero
#             )

#             # Asignar comisión libre
#             asignado = False
#             for i in range(1, 10):
#                 campo = f'cursando{i}'
#                 if getattr(estudiante, campo) is None:
#                     setattr(estudiante, campo, comision)
#                     estudiante.save()
#                     asignado = True
#                     break
#             if not asignado:
#                 return JsonResponse({
#                     "status": "error",
#                     "msg": "El estudiante ya está inscrito en el máximo de comisiones."
#                 }, status=400)

#             # ============================
#             # 🔹 Crear usuario vinculado
#             # ============================
#             ultimo_usuario = PerfilUsuario.objects.order_by('-id_usuario').first()
#             usuario_id = str(int(ultimo_usuario.id_usuario) + 1 if ultimo_usuario else 1).zfill(6)

#             usuario = PerfilUsuario.objects.create(
#                 id_usuario=usuario_id,
#                 id_estudiante=estudiante,
#                 nombre_usuario=documento,
#                 correo=email,
#                 rol="alumno",
#                 is_active=True
#             )
#             usuario.set_password("pass1234")
#             usuario.save()

#             # ============================
#             # 🔹 Registrar pago
#             # ============================
#             RegistroPago.objects.create(
#                 estudiante=estudiante,
#                 comision=comision,
#                 plataforma="web",
#                 medio_pago=medio_pago,
#                 estado_pago=estado_pago,
#                 monto=monto_dinamico,
#                 fecha_pago=timezone.now(),
#                 id_transaccion=id_transaccion,
#                 archivo_comprobante=comprobante
#             )

#             # ============================
#             # 💌 Envío de correos
#             # ============================
#             context_interno = {
#                 "nombre": nombre,
#                 "apellido": apellido,
#                 "email": email,
#                 "documento": documento,
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "pais": pais,
#                 "provincia": provincia,
#                 "telefono": telefono,
#                 "medio_pago": medio_pago,
#                 "estado_pago": estado_pago,
#                 "fecha": timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
#             }
#             html_interno = render_to_string("registration/registro_pago.html", context_interno)
#             text_interno = strip_tags(html_interno)

#             email_interno = EmailMultiAlternatives(
#                 subject="📥 Nuevo alumno inscripto y pago registrado",
#                 body=text_interno,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=["tecnomarema.ar@gmail.com"],
#             )
#             email_interno.attach_alternative(html_interno, "text/html")
#             email_interno.send()

#             # Correo al alumno
#             context_bienvenida = {
#                 "nombre": f"{nombre} {apellido}",
#                 "usuario": documento,
#                 "password": "pass1234",
#                 "curso": curso_nombre,
#                 "comision": comision.numero_comision,
#                 "reset_url": "https://tecnomarema.com/reset-password",
#             }
#             html_bienvenida = render_to_string("registration/bienvenida_paga.html", context_bienvenida)
#             text_bienvenida = strip_tags(html_bienvenida)

#             email_alumno = EmailMultiAlternatives(
#                 subject="🎓 Bienvenido/a a tu curso en Tecno Marema",
#                 body=text_bienvenida,
#                 from_email=settings.DEFAULT_FROM_EMAIL,
#                 to=[email],
#             )
#             email_alumno.attach_alternative(html_bienvenida, "text/html")
#             email_alumno.send()

#             # ============================
#             # 🔹 Respuesta final
#             # ============================
#             return JsonResponse({
#                 "status": "ok",
#                 "id_estudiante": nuevo_id,
#                 "id_usuario": usuario_id,
#                 "estado_pago": estado_pago
#             })

#         except Exception as e:
#             print("❌ ERROR EN INSCRIPCIÓN:", e)
#             return JsonResponse({"status": "error", "msg": str(e)}, status=500)

#     return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)


# views.py (ADAPTADO Y COMPLETO)

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import DatosDeEstudiantes, PerfilUsuario, Comision, RegistroPago, Curso
import mercadopago


@csrf_exempt
def guardar_datos_inscripcion_paga(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "msg": "Método no permitido"}, status=405)

    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)

    try:
        # ============================
        # RECEPCIÓN DE DATOS
        # ============================
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
        monto_dinamico = float(request.POST.get("monto", 0)) or 0.0
        id_estudiante_front = request.POST.get("id_estudiante", "").strip()

        # Mercado Pago
        token = request.POST.get("token")
        payment_method_id = request.POST.get("payment_method_id", "")
        installments = int(request.POST.get("installments", 1))

        # Transferencia
        comprobante = request.FILES.get("comprobante")

        # ============================
        # VALIDACIONES BÁSICAS
        # ============================
        if not all([nombre, apellido, documento, email, curso_id, comision_id, id_estudiante_front]):
            return JsonResponse({"status": "error", "msg": "Faltan datos obligatorios"}, status=400)

        # ============================
        # CURSO Y COMISIÓN
        # ============================
        try:
            curso_obj = Curso.objects.get(id_curso=curso_id)
        except Curso.DoesNotExist:
            return JsonResponse({"status": "error", "msg": "Curso no encontrado"}, status=400)

        try:
            comision = Comision.objects.get(numero_comision=comision_id, id_curso=curso_obj)
        except Comision.DoesNotExist:
            return JsonResponse({"status": "error", "msg": "Comisión no encontrada"}, status=400)

        # ============================
        # VALIDAR DUPLICADOS
        # ============================
        if DatosDeEstudiantes.objects.filter(dni=documento).exists():
            return JsonResponse({"status": "error", "msg": "DNI ya registrado"}, status=400)
        if DatosDeEstudiantes.objects.filter(correo=email).exists():
            return JsonResponse({"status": "error", "msg": "Email ya registrado"}, status=400)
        if PerfilUsuario.objects.filter(nombre_usuario=documento).exists():
            return JsonResponse({"status": "error", "msg": "DNI ya es usuario"}, status=400)
        if PerfilUsuario.objects.filter(correo=email).exists():
            return JsonResponse({"status": "error", "msg": "Email ya es usuario"}, status=400)

        # ============================
        # DETERMINAR MEDIO DE PAGO
        # ============================
        medio_pago_db = "mercadopago"  # valor por defecto
        medio_pago_texto = "Mercado Pago"
        estado_pago = "Pendiente"
        id_transaccion = ""

        if comprobante and not token:
            # TRANSFERENCIA
            medio_pago_db = "transferencia_bancaria"
            medio_pago_texto = "Transferencia bancaria"
            estado_pago = "Verificando"

        elif token and payment_method_id:
            # TARJETA O EFECTIVO
            if payment_method_id in ["rapipago", "pagofacil"]:
                medio_pago_db = payment_method_id
                medio_pago_texto = "Rapipago" if payment_method_id == "rapipago" else "Pago Fácil"
                estado_pago = "pendiente"

            elif payment_method_id.lower().startswith("deb"):
                medio_pago_db = "debito"
                medio_pago_texto = "Débito"
                estado_pago = "Aprobado"

            else:
                cuotas = max(1, installments)
                medio_pago_db = f"credito_{cuotas}"
                medio_pago_texto = f"Crédito en {cuotas} cuota{'s' if cuotas > 1 else ''}"
                estado_pago = "Aprobado"

            # PROCESAR PAGO CON MERCADO PAGO
            payment_data = {
                "transaction_amount": monto_dinamico,
                "token": token,
                "description": f"Inscripción {curso_obj.nombre_curso} - Comisión {comision_id}",
                "installments": installments,
                "payment_method_id": payment_method_id,
                "payer": {"email": email}
            }

            result = sdk.payment().create(payment_data)
            payment = result["response"]

            status_mp = payment["status"]

            # --- PAGOS EN EFECTIVO (Rapipago, Pago Fácil) ---
            if payment_method_id in ["rapipago", "pagofacil"] and status_mp == "pending" and payment.get("status_detail") == "pending_waiting_payment":
                # ÉXITO: el cliente debe pagar en efectivo
                id_transaccion = str(payment["id"])
                estado_pago = "pendiente"
                medio_pago_db = payment_method_id
                medio_pago_texto = "Rapipago" if payment_method_id == "rapipago" else "Pago Fácil"

            # --- TARJETA APROBADA ---
            elif status_mp == "approved":
                id_transaccion = str(payment["id"])
                estado_pago = "Aprobado"

            # --- CUALQUIER OTRO ESTADO (rechazado, error, etc.) ---
            else:
                return JsonResponse({
                    "status": "error",
                    "msg": f"Pago no aprobado: {payment.get('status_detail', status_mp)}"
                }, status=400)

            id_transaccion = str(payment["id"])
            estado_pago = "Aprobado"

        # ============================
        # GENERAR ID ESTUDIANTE
        # ============================
        if id_estudiante_front.startswith('TEMP') or not id_estudiante_front.isdigit():
            ultimo = DatosDeEstudiantes.objects.order_by('-id_estudiante').first()
            nuevo_id = str(int(ultimo.id_estudiante) + 1).zfill(6) if ultimo else "000001"
        else:
            nuevo_id = id_estudiante_front

        while DatosDeEstudiantes.objects.filter(id_estudiante=nuevo_id).exists():
            nuevo_id = str(int(nuevo_id) + 1).zfill(6)

        # ============================
        # CREAR ESTUDIANTE
        # ============================
        estudiante = DatosDeEstudiantes.objects.create(
            id_estudiante=nuevo_id,
            nombre=nombre, apellido=apellido, dni=documento, correo=email,
            fecha_nacimiento=fecha_nacimiento, pais=pais, provincia=provincia,
            telefono=telefono, genero=genero
        )

        # Asignar a comisión
        for i in range(1, 10):
            if getattr(estudiante, f'cursando{i}') is None:
                setattr(estudiante, f'cursando{i}', comision)
                estudiante.save()
                break
        else:
            estudiante.delete()
            return JsonResponse({"status": "error", "msg": "Máximo de comisiones alcanzado"}, status=400)

        # ============================
        # CREAR USUARIO
        # ============================
        ultimo_usuario = PerfilUsuario.objects.order_by('-id_usuario').first()
        usuario_id = str(int(ultimo_usuario.id_usuario) + 1).zfill(6) if ultimo_usuario else "000001"

        usuario = PerfilUsuario.objects.create(
            id_usuario=usuario_id, id_estudiante=estudiante,
            nombre_usuario=documento, correo=email, rol="alumno", is_active=True
        )
        usuario.set_password("pass1234")
        usuario.save()

        # ============================
        # REGISTRAR PAGO
        # ============================
        RegistroPago.objects.create(
            estudiante=estudiante, comision=comision, plataforma="web",
            medio_pago=medio_pago_db, estado_pago=estado_pago,
            monto=monto_dinamico, fecha_pago=timezone.now(),
            id_transaccion=id_transaccion, archivo_comprobante=comprobante
        )

        # ============================
        # CORREO INTERNO
        # ============================
        context_interno = {
            "nombre": nombre, "apellido": apellido, "email": email,
            "documento": documento, "curso": curso_obj.nombre_curso,
            "comision": comision.numero_comision, "pais": pais,
            "provincia": provincia, "telefono": telefono,
            "medio_pago": medio_pago_texto,  # ← Texto legible
            "fecha": timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        html_interno = render_to_string("registration/registro_pago.html", context_interno)
        email_interno = EmailMultiAlternatives(
            "Nuevo alumno inscripto", strip_tags(html_interno),
            settings.DEFAULT_FROM_EMAIL, ["tecnomarema.ar@gmail.com"]
        )
        email_interno.attach_alternative(html_interno, "text/html")
        email_interno.send()

        # ============================
        # CORREO AL ALUMNO
        # ============================
        context_bienvenida = {
            "nombre": f"{nombre} {apellido}", "usuario": documento,
            "password": "pass1234", "curso": curso_obj.nombre_curso,
            "comision": comision.numero_comision,
            "reset_url": "https://tecnomarema.com/reset-password"
        }
        html_bienvenida = render_to_string("registration/bienvenida_paga.html", context_bienvenida)
        email_alumno = EmailMultiAlternatives(
            "Bienvenido/a a Tecno Marema", strip_tags(html_bienvenida),
            settings.DEFAULT_FROM_EMAIL, [email]
        )
        email_alumno.attach_alternative(html_bienvenida, "text/html")
        email_alumno.send()

        return JsonResponse({
            "status": "ok",
            "id_estudiante": nuevo_id,
            "id_usuario": usuario_id,
            "medio_pago": medio_pago_texto
        })

    except Exception as e:
        print("ERROR:", e)
        import traceback; traceback.print_exc()
        return JsonResponse({"status": "error", "msg": "Error del servidor"}, status=500)


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
    return render(request, 'educativa/videos_desarrollo_web.html')

@session_required
def asistencia_alumnos(request):
    return render(request, 'educativa/asistencia_alumnos.html')

@session_required
def asistencia_general(request):
    return render(request, 'educativa/asistencia_general.html')

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
    }

    return render(request, 'educativa/valoraciones.html', contexto)



@session_required
def valoracion_alumno(request):
    return render(request, 'educativa/valoracion_alumno.html')

@session_required
def estadisticas(request):
    return render(request, 'educativa/estadisticas.html')


#-----------------------------------------------------------------

from django.db.models import Sum
from django.shortcuts import render, get_object_or_404
from .models import RegistroPago, DatosDeEstudiantes

@session_required
def saldo(request):
    usuario_id = request.session.get('usuario_id')

    if not usuario_id:
        return render(request, 'educativa/saldo.html', {
            'cursos_inscriptos': [],
            'nombre_usuario': 'Invitado',
            'mensaje': 'No hay estudiante identificado en sesión.'
        })

    # 🔧 CAMBIO ACÁ: usá el nombre correcto del campo PK
    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=usuario_id)

    cursos_inscriptos = []

    for i in range(1, 10):
        comision = getattr(estudiante, f'cursando{i}', None)
        if comision:
            curso = comision.id_curso
            pagos = RegistroPago.objects.filter(estudiante=estudiante, comision=comision)
            abonado = pagos.aggregate(total=Sum('monto'))['total'] or 0
            saldo = float(curso.precio_final) - float(abonado)

            cursos_inscriptos.append({
                'curso': curso,
                'comision': comision,
                'pagos': pagos,
                'abonado': abonado,
                'saldo': saldo,
            })

    context = {
        'cursos_inscriptos': cursos_inscriptos,
        'nombre_usuario': getattr(estudiante, 'nombre', 'Estudiante'),
    }

    return render(request, 'educativa/saldo.html', context)





#---------------------------------------------------------------------------


# @session_required
def faq(request):
    return render(request, 'educativa/faq.html')

@session_required
def redes(request):
    return render(request, 'educativa/redes.html')

@session_required
def contacto(request):
    return render(request, 'educativa/contacto.html')

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
    return render(request, 'educativa/perfil_alumno.html', {'usuario': usuario})

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

    return redirect('home')



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
comisiones = Comision.objects.all()

for comision in comisiones:
    estado = obtener_estado_comision(comision.fecha_inicio, comision.fecha_fin)
    comision.estado_comision = estado
    comision.save()  # Esto guarda el estado en la base de datos

###############################################################################
##---------------------traer nombres de clases-------------------------------##
###############################################################################

# from django.shortcuts import render, get_object_or_404
# from .models import Clase, Curso

# def curso_desarrollo_web_view(request):
#     curso = get_object_or_404(Curso, nombre="Desarrollo Web")
#     clases = Clase.objects.filter(curso=curso).order_by('numero_clase')
#     return render(request, 'curso_desarrollo_web.html', {
#         'clases': clases,
#         'curso': curso,
#     })

#------------------------------------------------------------------------------
# from .models import Clase

# def curso_view(request, curso_id):
#     clases = Clase.objects.filter(curso_id=curso_id, estado_clase='activo').order_by('numero_clase')
#     return render(request, 'educativa/curso.html', {'clases': clases})


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
        sdk = mercadopago.SDK("TU_ACCESS_TOKEN_AQUI")
        datos = json.loads(request.body)

        pago = {
            "transaction_amount": float(datos["transaction_amount"]),
            "token": datos["token"],
            "description": "Pago inscripción TecnoMarema",
            "installments": int(datos["installments"]),
            "payment_method_id": datos["payment_method_id"],
            "issuer_id": datos["issuer_id"],
            "payer": {
                "email": datos["payer"]["email"],
                "identification": datos["payer"]["identification"]
            }
        }

        resultado = sdk.payment().create(pago)
        return JsonResponse(resultado["response"])
    
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

from django.shortcuts import render
from .models import InscripcionClaseGratis

def guardar_inscripcion(request):
    if request.method == "POST":
        datos = request.POST

        inscripcion = InscripcionClaseGratis(
            nombre=datos.get("nombre"),
            apellido=datos.get("apellido"),
            telefono=datos.get("telefono"),
            pais=datos.get("pais"),
            email=datos.get("email"),
            dias=", ".join(datos.getlist("dias[]")),
            horarios=", ".join(datos.getlist("horarios[]")),
            nivel_pc=int(datos.get("nivel_pc")),
            exp_programacion=datos.get("exp_programacion"),
            nivel_programacion=int(datos.get("nivel_programacion")),
            tecnologias=", ".join(datos.getlist("tecnologias[]")),
        )
        inscripcion.save()
        return render(request, "educativa/gracias.html")
    else:
        return render(request, "404.html")  # opcional
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

@session_required
def listado_cursos_view(request):
    cursos = Curso.objects.all().order_by('id_curso') 
    return render(request, 'administrador/listado_cursos.html', {'cursos': cursos})

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
    admins = PerfilUsuario.objects.filter(is_staff=True)
    return render(request, 'administrador/listado_admins.html', {'usuarios': admins})

@session_required
def vista_chat_view(request):
    return render(request, 'administrador/chat_placeholder.html')



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
    actualizar_lectura(chat_general_obj, usuario)

    mensajes = chat_general_obj.mensajes.select_related('remitente').order_by('creado')

    return render(request, 'educativa/chat.html', {
        'chat_general': chat_general_obj,
        'chat': chat_general_obj,
        'mensajes': mensajes,
        'usuario': usuario,
        'nombre_usuario': nombre_usuario,
        'usuarios_destino': [],
        'badges': {},
        'chats_comision': {},
    })



#####################################################################################
###----------------------------el polling del chat---------------------------------##
#####################################################################################

from zoneinfo import ZoneInfo
from django.utils import timezone
from django.http import JsonResponse
from .models import Chat  # Asegurate de tener este import

def obtener_mensajes(request):
    chat_general = Chat.objects.get(tipo='general')
    mensajes = chat_general.mensajes.select_related('remitente').order_by('creado')

    tz_arg = ZoneInfo('America/Argentina/Buenos_Aires')

    lista = []
    for m in mensajes:
        local_time = timezone.localtime(m.creado, tz_arg).strftime("%d/%m %H:%M")
        lista.append({
            'id': m.id,
            'usuario': m.remitente.nombre_usuario,
            'texto': m.texto,
            'hora': local_time,
            'fecha': m.creado.isoformat(),  # 👈 AÑADÍ ESTA LÍNEA
            'creado': m.creado.isoformat(), # 👈 Y TAMBIÉN ESTA SI TU JS LA USA
            'archivo_url': m.archivo.url if m.archivo else None,
            'archivo_name': m.archivo.name.split('/')[-1] if m.archivo else None,
            'destacado': m.destacado,  # 👈 AGREGÁ ESTA LÍNEA
        })

    return JsonResponse({'mensajes': lista})

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
            'hora': m.creado.strftime("%d/%m %H:%M"),
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

    actualizar_lectura(chat, usuario)

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

    # Obtener o crear chat privado único
    chat = obtener_chat_privado(remitente, destinatario)

    mensajes = chat.mensajes.select_related('remitente').order_by('creado')

    # Obtener comisiones del remitente para mostrar posibles usuarios destino
    comisiones = []
    if remitente.id_estudiante:
        est_rem = remitente.id_estudiante
        comisiones = [
            est_rem.cursando1, est_rem.cursando2, est_rem.cursando3, est_rem.cursando4,
            est_rem.cursando5, est_rem.cursando6, est_rem.cursando7, est_rem.cursando8, est_rem.cursando9
        ]
        comisiones = [c for c in comisiones if c]

    # Alumnos que comparten esas comisiones
    alumnos = PerfilUsuario.objects.filter(
        Q(rol='profesor') | Q(rol='profesor') | Q(rol='tutor'),
        id_estudiante__in=DatosDeEstudiantes.objects.filter(
            Q(cursando1__in=comisiones) | Q(cursando2__in=comisiones) |
            Q(cursando3__in=comisiones) | Q(cursando4__in=comisiones) |
            Q(cursando5__in=comisiones) | Q(cursando6__in=comisiones) |
            Q(cursando7__in=comisiones) | Q(cursando8__in=comisiones) |
            Q(cursando9__in=comisiones)
        )
    )

    # Tutores y profesores desde las comisiones
    tutores = []
    profesores = []
    for com in comisiones:
        if hasattr(com, 'tutores'):
            tutores.extend(com.tutores.all())
        elif hasattr(com, 'tutor') and com.tutor:
            tutores.append(com.tutor)
        if hasattr(com, 'profesor') and com.profesor:
            profesores.append(com.profesor)

    usuarios_destino = set(alumnos).union(tutores).union(profesores)
    usuarios_destino.discard(remitente)

    actualizar_lectura(chat, remitente)

    return render(request, 'educativa/chat.html', {
        'chat': chat,
        'mensajes': mensajes,
        'usuario': remitente,
        'nombre_usuario': remitente.nombre_usuario,
        'destinatario': destinatario,
        'usuarios_destino': list(usuarios_destino),
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
        'hora': m.creado.strftime("%d/%m %H:%M"),
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
from .models import Chat, LecturaMensaje, PerfilUsuario
from django.http import JsonResponse
from .models import Chat, PerfilUsuario, Mensaje

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

    chats = Chat.objects.filter(participantes=usuario).select_related('comision').prefetch_related('mensajes')

    for chat in chats:
        mensajes_no_leidos = chat.mensajes.filter(leido=False).exclude(remitente=usuario)

        if chat.tipo == 'general':
            data['general'] = mensajes_no_leidos.count()

        elif chat.tipo == 'comision' and chat.comision:
            data['comisiones'][chat.comision.id_comision] = mensajes_no_leidos.count()

        elif chat.tipo == 'privado':
            otro = chat.participantes.exclude(id=usuario.id).first()
            if otro and mensajes_no_leidos.exists():
                ultimo = mensajes_no_leidos.last()
                data['privados'].append({
                    'id_usuario': otro.id_usuario,
                    'nombre': otro.nombre_usuario,
                    'nuevos': mensajes_no_leidos.count(),
                    'ultimo_texto': ultimo.texto[:30] if ultimo.texto else '',
                    'hora': ultimo.creado.strftime('%H:%M'),
                })

    return JsonResponse(data)

#-------------------------------------------------------------------------------------------------------------------

from .models import LecturaMensaje

def actualizar_lectura(chat, usuario):
    ultimo = chat.mensajes.order_by('-creado').first()
    if not ultimo:
        return
    lectura, _ = LecturaMensaje.objects.get_or_create(usuario=usuario, chat=chat)
    lectura.ultimo_mensaje_leido = ultimo
    lectura.save()



###################################################################################################################
###-----------------------Estadisticas generales, cursos, comisiones y clase------------------------------------###
###################################################################################################################

from django.http import JsonResponse
from .models import ValoracionAlumno, ClaseComision
from django.db.models import Avg, Count
from collections import defaultdict

def obtener_estadisticas_valoraciones(request):
    clase_id = request.GET.get('clase')
    ambito = request.GET.get('ambito')

    valoraciones = ValoracionAlumno.objects.all()

    if clase_id and clase_id.isdigit():
        clase_id_num = int(clase_id)

        if ambito == "clase":
            valoraciones = valoraciones.filter(clase_id=clase_id_num)

        elif ambito == "comision":
            clase = ClaseComision.objects.filter(id=clase_id_num).first()
            if clase:
                valoraciones = valoraciones.filter(comision_id=clase.comision.id_comision)

        elif ambito == "curso":
            clase = ClaseComision.objects.filter(id=clase_id_num).first()
            if clase and clase.comision and clase.comision.id_curso:
                valoraciones = valoraciones.filter(curso_id=clase.comision.id_curso.id_curso)

    # Recuento preferencia_clase
    liked_counts = valoraciones.values('preferencia_clase').annotate(total=Count('valoracion_alumno_id'))

    # Promedios generales
    promedio = valoraciones.aggregate(
        profe=Avg('rol_profe'),
        contenido=Avg('contenido'),
        plataforma=Avg('plataforma'),
        streaming=Avg('streaming')
    )

    total_valoraron = valoraciones.count()
    total_alumnos = valoraciones.values('id_estudiante').distinct().count()
    total_no_valoraron = max(0, total_alumnos - total_valoraron)

    # Estadísticas por pregunta: distribución 1 a 10
    def contar_valores_por_pregunta(campo):
        # Diccionario de 1 a 10 con conteo inicial en 0
        conteo = {str(i): 0 for i in range(1, 11)}
        valores = valoraciones.values(campo).annotate(cantidad=Count('valoracion_alumno_id'))
        for v in valores:
            valor = v[campo]
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
        'promedios': promedio,
        'valoraron_vs_no': {
            'valoraron': total_valoraron,
            'no_valoraron': total_no_valoraron
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

from django.shortcuts import render
from django.db.models import Count
from .models import InscripcionClaseGratis
from plataforma.decorators import session_required
import itertools
import json

@session_required
def alumnos_clase1_html(request):
    qs = InscripcionClaseGratis.objects.all().order_by('-creado')

    def split_counts(lst):
        flat = list(itertools.chain.from_iterable([x.split(', ') for x in lst if x]))
        return {k: flat.count(k) for k in set(flat)}

    nivel_pc_counts = qs.values('nivel_pc').annotate(count=Count('nivel_pc')).order_by('nivel_pc')
    exp_prog_counts = qs.values('exp_programacion').annotate(count=Count('exp_programacion'))
    nivel_prog_counts = qs.values('nivel_programacion').annotate(count=Count('nivel_programacion')).order_by('nivel_programacion')

    graf_dias = split_counts(qs.values_list('dias', flat=True))
    graf_horarios = split_counts(qs.values_list('horarios', flat=True))
    graf_tecnos = split_counts(qs.values_list('tecnologias', flat=True))

    contexto = {
        "inscripciones": qs,

        "graf_dias_labels": json.dumps(list(graf_dias.keys())),
        "graf_dias_data": json.dumps(list(graf_dias.values())),

        "graf_horarios_labels": json.dumps(list(graf_horarios.keys())),
        "graf_horarios_data": json.dumps(list(graf_horarios.values())),

        "graf_nivel_pc_labels": json.dumps([str(item['nivel_pc']) for item in nivel_pc_counts]),
        "graf_nivel_pc_data": json.dumps([item['count'] for item in nivel_pc_counts]),

        "graf_exp_prog_labels": json.dumps([item['exp_programacion'] for item in exp_prog_counts]),
        "graf_exp_prog_data": json.dumps([item['count'] for item in exp_prog_counts]),

        "graf_nivel_prog_labels": json.dumps([str(item['nivel_programacion']) for item in nivel_prog_counts]),
        "graf_nivel_prog_data": json.dumps([item['count'] for item in nivel_prog_counts]),

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

from django.shortcuts import render
from .models import ValoracionAlumno

def listado_valoraciones(request):
    valoraciones = ValoracionAlumno.objects.all().order_by('-fecha_valoracion')
    return render(request, 'administrador/listado_valoraciones.html', {'valoraciones': valoraciones})

##################################################################################################
####----------------------------listado de proyectos------------------------------------------####
##################################################################################################

def listado_proyectos(request):
    entregas = EntregaProyecto.objects.select_related("estudiante", "curso", "comision")
    return render(request, "administrador/listado_proyectos.html", {"entregas": entregas})

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

from django.shortcuts import render, redirect
from .forms import SuscriptorForm
from django.contrib import messages

def newsletter_view(request):
    if request.method == 'POST':
        form = SuscriptorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Gracias por suscribirte!')
            return redirect('inicio')  # Cambiá esto al nombre real de tu URL o plantilla
    else:
        form = SuscriptorForm()
    
    return render(request, 'home.html', {'form': form})


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