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

def cursos(request):
    return render(request, 'educativa/cursos.html')

def cursos_view(request):
    return render(request, 'cursos.html') #agregado por la sesion que devuelva usuario

def desarrollo_web_compra(request):
    return render(request, 'educativa/desarrollo_web_compra.html')

def inscripcion(request):
    return render(request, 'educativa/inscripcion.html')

def terminos_y_condiciones(request):
    return render(request, 'educativa/terminos_y_condiciones.html')

# --- Vistas privadas (requieren login) ---
# @session_required
# def mis_cursos(request):
#     return render(request, 'educativa/mis_cursos.html')
# mis cursos inician
@session_required
def desarrollo_web(request):
    return render(request, 'educativa/desarrollo_web.html')

@session_required
def inteligencia_artificial(request):
    return render(request, 'educativa/inteligencia_artificial.html')

@session_required
def python_curso(request):
    return render(request, 'educativa/python_curso.html')

@session_required
def javascript_curso(request):
    return render(request, 'educativa/javascript_curso.html')
# mis cursos finaliza

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

from django.db.models import Count
from django.shortcuts import render
from plataforma.decorators import session_required
from plataforma.models import ValoracionAlumno

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

@session_required
def saldo(request):
    return render(request, 'educativa/saldo.html')

@session_required
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

        # Cargar cursos y comisiones de cursando1, cursando2 y cursando3 hasta la 9 si llega haber mas de nueve cursos se debe actualizar
        comisiones = []
        for comision_id in [estudiante.cursando1_id, estudiante.cursando2_id, estudiante.cursando3_id, estudiante.cursando4_id, estudiante.cursando5_id , estudiante.cursando6_id, estudiante.cursando7_id, estudiante.cursando8_id , estudiante.cursando9_id ]:
            if comision_id:
                try:
                    comision = Comision.objects.select_related('id_curso').get(id_comision=comision_id)
                    comisiones.append(comision)
                except Comision.DoesNotExist:
                    continue

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

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import PerfilUsuario
from .decorators import session_required

@session_required
def desarrollo_web(request):
    nombre_usuario = request.session.get('usuario_logueado', 'AnonymousUser')
    es_autenticado = 'usuario_logueado' in request.session

    try:
        usuario = PerfilUsuario.objects.select_related('id_estudiante').get(nombre_usuario=nombre_usuario)
        estudiante = usuario.id_estudiante

        contexto = {
            'usuario': usuario,
            'estudiante': estudiante,
            'nombre_usuario': nombre_usuario,
            'es_autenticado': es_autenticado,
        }
        return render(request, 'educativa/desarrollo_web.html', contexto)

    except PerfilUsuario.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login')



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
from .models import DatosDeEstudiantes, Clase, ValoracionAlumno

def mostrar_formulario_valoracion(request, clase_id):
    id_usuario = request.session.get('usuario_id')
    nombre_usuario = request.session.get('usuario_logueado')

    if not id_usuario or not nombre_usuario:
        return redirect('login')  # Por si alguien accede sin sesión activa

    # DEBUG para chequear que la sesión esté bien
    print("DEBUG SESSION usuario_id:", id_usuario)
    print("DEBUG SESSION usuario_logueado:", nombre_usuario)

    estudiante = get_object_or_404(DatosDeEstudiantes, id_estudiante=id_usuario)
    clase = get_object_or_404(Clase, id=clase_id)

    contexto = {
        'id_estudiante': str(id_usuario),
        'id_usuario': str(id_usuario),
        'nombre_usuario': str(nombre_usuario),
        'clase': clase,
    }
    return render(request, 'educativa/guardar_valoracion.html', contexto)


from django.shortcuts import redirect, get_object_or_404
from .models import ValoracionAlumno, Clase
from django.utils import timezone

def guardar_valoracion(request):
    if request.method == 'POST':
        # id_estudiante = request.session.get('usuario_id')
        # nombre_usuario = request.session.get('usuario_logueado')

        # id_estudiante = request.POST.get('id_estudiante')
        # nombre_usuario = request.POST.get('nombre_usuario')
        # clase_id = request.POST.get('clase_id')

        id_estudiante = request.POST.get('id_estudiante')
        id_usuario = request.POST.get('id_usuario')
        nombre_usuario = request.POST.get('nombre_usuario')
        clase_id = request.POST.get('clase_id')

        print("VALORES POST crudos:")
        print("id_estudiante:", id_estudiante)
        print("id_usuario:", id_usuario)
        print("nombre_usuario:", nombre_usuario)
        print("clase_id:", clase_id)

        if not id_estudiante or not nombre_usuario or not clase_id:
            return redirect('mis_cursos')

        clase = get_object_or_404(Clase, id=clase_id)


                # 🟢 DEBUG: imprimir datos antes de guardar
        print("Guardando valoración de:", nombre_usuario, "para clase:", clase_id)
        print("Preferencia:", request.POST.get('preferencia_clase', ''))
        print("Rol:", request.POST.get('rol_profe', ''))
        print("Contenido:", request.POST.get('contenido', ''))
        print("Plataforma:", request.POST.get('plataforma', ''))
        print("Streaming:", request.POST.get('streaming', ''))
        print("Comentarios:", request.POST.get('comentarios', ''))

        ValoracionAlumno.objects.create(
            id_estudiante=id_estudiante,
            id_usuario=id_estudiante,
            nombre_usuario=nombre_usuario,
            clase=clase,
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
from django.core.mail import send_mail
from django.conf import settings
from django.db import IntegrityError
from .forms import AltaAlumnoForm
from .models import DatosDeEstudiantes, PerfilUsuario
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def alta_alumno_view(request):
    mostrar_modal_error = False

    if request.method == 'POST':
        form = AltaAlumnoForm(request.POST)
        if form.is_valid():
            datos = form.save(commit=False)

            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            correo = datos.correo

            if PerfilUsuario.objects.filter(nombre_usuario=username).exists():
                form.add_error('username', 'Este nombre de usuario ya está en uso. Elegí otro.')
                mostrar_modal_error = True
            else:
                try:
                    # 1. Guardamos el estudiante para que exista el id_estudiante
                    datos.save()

                    # 2. Creamos o actualizamos el PerfilUsuario asignando id_usuario = id_estudiante
                    usuario, creado = PerfilUsuario.objects.update_or_create(
                        id_usuario=datos.id_estudiante,
                        defaults={
                            'id_estudiante': datos,          # FK a DatosDeEstudiantes
                            'nombre_usuario': username,
                            'correo': correo,
                            'is_active': True,
                            'is_staff': False,
                        }
                    )

                    # 3. Seteamos la contraseña (en caso de update no queda set)
                    usuario.set_password(password)
                    usuario.save()

                    # 4. Enviar email de confirmación

                    # Construir URL con reverse
                    reset_path = reverse('password_reset')
                    reset_url = request.build_absolute_uri(reset_path)

                    # Renderizar HTML del correo
                    html_content = render_to_string('registration/bienvenida_alumno.html', {
                        'nombre': datos.nombre,
                        'usuario': username,
                        'password': password,
                        'reset_url': reset_url,
                    })

                    # Crear email con HTML
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

# @session_required
# def curso_detalle_view(request, id_curso):
#     # Obtengo el nombre de usuario logueado de la sesión
#     nombre_usuario = request.session.get('usuario_logueado')
#     if not nombre_usuario:
#         return redirect('login')

#     # Obtengo el objeto PerfilUsuario con su relación a id_estudiante
#     try:
#         usuario = PerfilUsuario.objects.select_related('id_estudiante').get(nombre_usuario=nombre_usuario)
#         estudiante = usuario.id_estudiante
#     except PerfilUsuario.DoesNotExist:
#         messages.error(request, 'Usuario no encontrado.')
#         return redirect('login')

#     # Busco el curso según el id_curso que llega por URL
#     curso = get_object_or_404(Curso, id_curso=id_curso)

#     # Obtengo las comisiones que cursa el estudiante (pueden ser None)
#     comisiones_estudiante = [
#         estudiante.cursando1,
#         estudiante.cursando2,
#         estudiante.cursando3,
#         estudiante.cursando4,
#         estudiante.cursando5,
#         estudiante.cursando6,
#         estudiante.cursando7,
#         estudiante.cursando8,
#         estudiante.cursando9,
#     ]

#     # Busco la comisión actual que corresponde al curso
#     comision_actual = next(
#         (com for com in comisiones_estudiante if com and com.id_curso == curso),
#         None
#     )

#     # Obtengo todas las clases del curso ordenadas por número de clase
#     clases_del_curso = curso.clases.filter(estado_clase='Activo').order_by('numero_clase')

#     # Normalizo nombre del curso para elegir el template correcto
#     nombre_normalizado = curso.nombre_curso.strip().lower()

#     templates_por_curso = {
#         "desarrollo web": "educativa/curso_desarrollo_web.html",
#         "inteligencia artificial": "educativa/curso_ia.html",
#         "python": "educativa/curso_python.html",
#         "javascript": "educativa/curso_javascript.html",
#     }

#     template_a_usar = templates_por_curso.get(nombre_normalizado, "educativa/curso_detalle.html")

#     contexto = {
#         'usuario': usuario,
#         'estudiante': estudiante,
#         'curso': curso,
#         'comision': comision_actual,
#         'nombre_usuario': nombre_usuario,
#         'es_autenticado': True,
#         'clases': clases_del_curso,  # <-- Aquí le paso las clases al template
        
#     }

#     return render(request, template_a_usar, contexto)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import PerfilUsuario, Curso, Comision, Clase, ClaseComision
from .decorators import session_required
from .models import AsistenciaClase

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

    # 4. Verificar que el estudiante esté inscripto en esa comisión
    if comision not in [
        estudiante.cursando1, estudiante.cursando2, estudiante.cursando3,
        estudiante.cursando4, estudiante.cursando5, estudiante.cursando6,
        estudiante.cursando7, estudiante.cursando8, estudiante.cursando9,
    ]:
        messages.error(request, 'No estás inscripto en esta comisión.')
        return redirect('mis_cursos')

    # 5. Obtener clases activas del curso
    clases_del_curso = curso.clases.filter(estado_clase='Activo').order_by('numero_clase')

    # 6. Obtener las instancias de ClaseComision para esta comisión
    clases_comisionadas = ClaseComision.objects.filter(
        comision=comision,
        clase__in=clases_del_curso
    ).select_related('clase')

    clasecomision_dict = {cc.clase_id: cc for cc in clases_comisionadas}

    # 7. Determinar template según el curso
    nombre_normalizado = curso.nombre_curso.strip().lower()
    templates_por_curso = {
        "desarrollo web": "educativa/curso_desarrollo_web.html",
        "inteligencia artificial": "educativa/curso_ia.html",
        "python": "educativa/curso_python.html",
        "javascript": "educativa/curso_javascript.html",
    }

    template_a_usar = templates_por_curso.get(nombre_normalizado, "educativa/curso_detalle.html")

    # Obtener asistencias del estudiante
    asistencias = AsistenciaClase.objects.filter(estudiante=estudiante)
    clases_presentes_ids = list(asistencias.values_list('clase_id', flat=True))

    # 8. Renderizar
    contexto = {
        'usuario': usuario,
        'estudiante': estudiante,
        'curso': curso,
        'comision': comision,
        'nombre_usuario': nombre_usuario,
        'es_autenticado': True,
        'clases': clases_del_curso,
        'clasescomision': clasecomision_dict,
        'clases_presentes_ids': clases_presentes_ids,  # ✅ AHORA SÍ
    }

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

from django.shortcuts import render, get_object_or_404
from .models import Clase, Curso

def curso_desarrollo_web_view(request):
    curso = get_object_or_404(Curso, nombre="Desarrollo Web")
    clases = Clase.objects.filter(curso=curso).order_by('numero_clase')
    return render(request, 'curso_desarrollo_web.html', {
        'clases': clases,
        'curso': curso,
    })

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

        # Carga de datos específicos para una comisión (ClaseComision)
        elif 'guardar_clase_comision' in request.POST:
            form = ClaseComisionForm(request.POST)
            if form.is_valid():
                form.save()
                comision_id = request.POST.get('comision')
                # redirect con parámetro para mostrar modal
                return redirect(f'/alta_clase_comision/?id_comision={comision_id}&guardado=1')
            else:
                print(form.errors)  # Debug en consola
    else:
        form = ClaseComisionForm()

    comision_id = request.GET.get('id_comision')
    if comision_id:
        comision_seleccionada = Comision.objects.get(id_comision=comision_id)
        clases = Clase.objects.filter(curso=comision_seleccionada.id_curso).order_by('numero_clase')

    guardado_exitoso = request.GET.get('guardado') == '1'

    nuevo_id_clase = get_random_string(length=8).upper()

    return render(request, 'educativa/alta_clase_comision.html', {
        'comisiones': comisiones,
        'comision_seleccionada': comision_seleccionada,
        'clases': clases,
        'nuevo_id_clase': nuevo_id_clase,
        'form': form,
        'guardado_exitoso': guardado_exitoso
    })
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

# def participantes_view(request, curso_id):
#     # Aquí el código que maneja el curso con id=curso_id
#     curso = Curso.objects.get(id=curso_id)
#     # luego filtras profesores, tutores y alumnos por curso
#     profesores = PerfilUsuario.objects.filter(rol='profesor', curso=curso)
#     tutores = PerfilUsuario.objects.filter(rol='tutor', curso=curso)
#     alumnos = PerfilUsuario.objects.filter(rol='alumno', curso=curso)

#     return render(request, 'educativa/participantes.html', {
#         'profesores': profesores,
#         'tutores': tutores,
#         'alumnos': alumnos,
#         'cantidad_alumnos': alumnos.count(),
#         'curso': curso,
#     })


# from django.shortcuts import render, get_object_or_404
# from plataforma.models import Curso, PerfilUsuario

# def participantes_view(request, curso_id):
#     curso = get_object_or_404(Curso, id_curso=curso_id)

#     # Ajusta esto al campo real de tu modelo PerfilUsuario que relacione al curso
#     profesores = PerfilUsuario.objects.filter(rol='profesor', curso_asignado=curso)
#     tutores = PerfilUsuario.objects.filter(rol='tutor', curso_asignado=curso)
#     # alumnos = PerfilUsuario.objects.filter(rol='alumno', curso_asignado=curso)
#     alumnos = PerfilUsuario.objects.filter(rol='alumno', id_estudiante__curso_asignado=curso_id)


#     contexto = {
#         'curso': curso,
#         'profesores': profesores,
#         'tutores': tutores,
#         'alumnos': alumnos,
#         'cantidad_alumnos': alumnos.count(),
#     }
#     return render(request, 'educativa/participantes.html', contexto)


# from django.shortcuts import render, get_object_or_404
# from .models import PerfilUsuario, Curso

# def participantes_view(request, curso_id):
#     curso = get_object_or_404(Curso, id_curso=curso_id)

#     profesores = PerfilUsuario.objects.filter(rol='profesor', id_estudiante__curso_asignado=curso_id)
#     tutores = PerfilUsuario.objects.filter(rol='tutor', id_estudiante__curso_asignado=curso_id)
#     alumnos = PerfilUsuario.objects.filter(rol='alumno', id_estudiante__curso_asignado=curso_id)

#     context = {
#         'curso': curso,
#         'profesores': profesores,
#         'tutores': tutores,
#         'alumnos': alumnos,
#         'cantidad_alumnos': alumnos.count(),
#     }
#     return render(request, 'educativa/participantes.html', context)

from django.shortcuts import render, get_object_or_404
from .models import PerfilUsuario, Curso, Comision, DatosDeEstudiantes
from django.db.models import Q

from django.shortcuts import render, get_object_or_404
from .models import PerfilUsuario, Curso, Comision, DatosDeEstudiantes
from django.db.models import Q

def participantes_view(request, numero_comision, id_curso):
    # Buscar el curso y la comisión específica
    curso = get_object_or_404(Curso, id_curso=id_curso)
    comision = get_object_or_404(Comision, numero_comision=numero_comision, id_curso=curso)

    # Buscar estudiantes cursando esa comisión en cualquiera de los campos cursando1-9
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

    context = {
        'curso': curso,
        'comision': comision,
        'profesores': profesores,
        'tutores': tutores,
        'alumnos': alumnos,
        'cantidad_alumnos': alumnos.count(),
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

from .models import Clase, DatosDeEstudiantes, AsistenciaClase
from django.utils import timezone
from django.shortcuts import redirect
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from plataforma.decorators import session_required

from .models import Clase, DatosDeEstudiantes, AsistenciaClase
from django.shortcuts import redirect
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from plataforma.decorators import session_required

def agregar_parametro(url, clave, valor):
    partes = urlparse(url)
    query = dict(parse_qsl(partes.query))
    query[clave] = valor
    nueva_query = urlencode(query)
    return urlunparse(partes._replace(query=nueva_query))

# @session_required
# def marcar_presente(request, clase_id):
#     estudiante_id = request.session.get('usuario_id')
#     if not estudiante_id:
#         return redirect('login')

#     clase = Clase.objects.get(id=clase_id)
#     estudiante = DatosDeEstudiantes.objects.get(id_estudiante=estudiante_id)

#     ya_registrada = AsistenciaClase.objects.filter(estudiante=estudiante, clase=clase).exists()

#     if ya_registrada:
#         referer = request.META.get('HTTP_REFERER', '/')
#         return redirect(agregar_parametro(referer, 'presente', '1'))

#     asistencia = AsistenciaClase(estudiante=estudiante, clase=clase)
#     asistencia.guardar_detalles()
#     asistencia.save()

#     return redirect(request.META.get('HTTP_REFERER', 'mis_cursos'))

from django.http import JsonResponse
from django.shortcuts import redirect
from .models import Clase, DatosDeEstudiantes, AsistenciaClase
from .decorators import session_required

@session_required
def marcar_presente(request, clase_id):
    estudiante_id = request.session.get('usuario_id')
    if not estudiante_id:
        return redirect('login')

    clase = Clase.objects.get(id=clase_id)
    estudiante = DatosDeEstudiantes.objects.get(id_estudiante=estudiante_id)

    if AsistenciaClase.objects.filter(estudiante=estudiante, clase=clase).exists():
        # Si ya marcó presente, mostramos el modal después de recargar
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ya_presente": True})
        return redirect(f"{request.META.get('HTTP_REFERER', 'mis_cursos')}?presente=1")

    asistencia = AsistenciaClase(estudiante=estudiante, clase=clase)
    asistencia.guardar_detalles()
    asistencia.save()

    # ✅ Redirecciona con `?presente=1` para mostrar el modal
    return redirect(f"{request.META.get('HTTP_REFERER', 'mis_cursos')}?presente=1")


################################################################################################
###-----------------mensaje de agradecimiento por la valoracion de la clase------------------###
################################################################################################

from django.shortcuts import render

def agradecimiento(request):
    return render(request, 'educativa/agradecimiento.html')