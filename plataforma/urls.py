# # plataforma/urls.py
from django.urls import path
from django.contrib.auth.views import (
    LogoutView,
    PasswordResetDoneView,
    PasswordResetCompleteView
)
from . import views
from .views import CustomPasswordResetView, CustomPasswordResetConfirmView
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views

from django.conf import settings
from django.conf.urls.static import static
import os

from .views import alta_alumno_view
from .views import alumno_alta_exitosa_view


# from .views import el_curso_view
from .views import curso_detalle_view

urlpatterns = [
    # ---------- PÚBLICAS ----------
    path('', views.inicio, name='inicio'),  # Página de inicio - http://127.0.0.1:8000/
    path('home/', views.home, name='home'),  # Página principal - http://127.0.0.1:8000/home/
    path('login/', views.login_view, name='login'),  # Login de usuario - http://127.0.0.1:8000/login/
    path('logout/', LogoutView.as_view(), name='logout'),  # Cerrar sesión - http://127.0.0.1:8000/logout/
    # path('logout/', LogoutView.as_view(next_page='login'), name='logout'),  # Cerrar sesión con redirección

    path('inscripcion/', views.inscripcion, name='inscripcion'),  # Registro o inscripción - http://127.0.0.1:8000/inscripcion/
    path('cursos/', views.cursos, name='cursos'),  # Listado de cursos - http://127.0.0.1:8000/cursos/
    path('desarrollo_web_compra/', views.desarrollo_web_compra, name='desarrollo_web_compra'),  # Compra de curso - http://127.0.0.1:8000/desarrollo_web_compra/
    path('terminos_y_condiciones/', views.terminos_y_condiciones, name='terminos_y_condiciones'),  # Términos y condiciones - http://127.0.0.1:8000/terminos_y_condiciones/

    # ---------- PRIVADAS (requieren sesión) ----------
    path('mis_cursos/', views.mis_cursos, name='mis_cursos'),  # Cursos del usuario - http://127.0.0.1:8000/mis_cursos/
    # path('desarrollo_web/', views.desarrollo_web, name='desarrollo_web'),  # Acceso al curso - http://127.0.0.1:8000/desarrollo_web/
    # path('inteligencia_artificial/', views.inteligencia_artificial, name='inteligencia_artificial'),  # Acceso al curso - http://127.0.0.1:8000/inteligencia_artificial/
    # path('python_curso/', views.python_curso, name='python_curso'),  # Acceso al curso - http://127.0.0.1:8000/python_curso/
    # path('javascript_curso/', views.javascript_curso, name='javascript_curso'),  # Acceso al curso - http://127.0.0.1:8000/javascript_curso/
    path('videos_desarrollo_web/', views.videos_desarrollo_web, name='videos_desarrollo_web'),  # Videos del curso - http://127.0.0.1:8000/videos_desarrollo_web/
    path('asistencia_alumnos/', views.asistencia_alumnos, name='asistencia_alumnos'),  # Asistencia de alumnos - http://127.0.0.1:8000/asistencia_alumnos/
    path('asistencia_general/', views.asistencia_general, name='asistencia_general'),  # Asistencia general - http://127.0.0.1:8000/asistencia_general/
    path('valoraciones/', views.valoraciones, name='valoraciones'),  # Valoraciones de cursos - http://127.0.0.1:8000/valoraciones/
    # path('valoracion_alumno/', views.valoracion_alumno, name='valoracion_alumno'),  # Valoración individual - http://127.0.0.1:8000/valoracion_alumno/<int:clase_id>
    # path('valoracion_alumno/<int:clase_id>/', views.mostrar_formulario_valoracion, name='valoracion_alumno'), # Valoración individual - http://127.0.0.1:8000/valoracion_alumno/<int:clase_id>

    path('valoraciones/curso/<str:curso_id>/comision/<str:comision_id>/', views.valoraciones_filtradas, name='valoraciones_filtradas'),


    path('valoracion_alumno/<str:curso_id>/comision/<str:comision_id>/estudiante/<str:estudiante_id>/valoracion/<int:numero_clase>/', views.mostrar_formulario_valoracion, name='valoracion_alumno'),


    path('estadisticas/', views.estadisticas, name='estadisticas'),  # Estadísticas - http://127.0.0.1:8000/estadisticas/
    path('saldo/', views.saldo, name='saldo'),  # Saldo del usuario - http://127.0.0.1:8000/saldo/
    path('faq/', views.faq, name='faq'),  # Preguntas frecuentes - http://127.0.0.1:8000/faq/
    path('redes/', views.redes, name='redes'),  # Redes sociales o comunidad - http://127.0.0.1:8000/redes/
    path('contacto/', views.contacto, name='contacto'),  # Contacto o soporte - http://127.0.0.1:8000/contacto/


    path("enviar-mensaje", views.enviar_mensaje, name="enviar_mensaje"),

    path('perfil/', views.perfil_alumno_view, name='perfil'),  # Perfil del alumno - http://127.0.0.1:8000/perfil/

    # ---------- RECUPERACIÓN DE CONTRASEÑA ----------
    path('reset/password/', CustomPasswordResetView.as_view(), name='password_reset'),  # Solicitud de reset - http://127.0.0.1:8000/reset/password/
    path('reset/password/sent/', PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'), name='password_reset_done'),  # Confirmación email enviado - http://127.0.0.1:8000/reset/password/sent/
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url=reverse_lazy('login')
    ), name='password_reset_confirm'),  # Nueva contraseña - http://127.0.0.1:8000/reset/<uidb64>/<token>/


    path('logout_all/', views.logout_all_view, name='logout_all'),


    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),

    path('perfil/cambiar_foto/', views.subir_foto_perfil, name='cambiar_foto'),

    path('perfil/eliminar_foto/', views.eliminar_foto, name='eliminar_foto'),

        # path('editar-foto/', views.editar_foto, name='editar_foto'),


    path('reset/done/', PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'), name='password_reset_complete'),  # Reset completado - http://127.0.0.1:8000/reset/done/



    # Mostrar el formulario de valoración
    path('valorar_clase/<int:clase_id>/', views.mostrar_formulario_valoracion, name='mostrar_formulario_valoracion'),

    # Guardar la valoración
    path('guardar_valoracion/', views.guardar_valoracion, name='guardar_valoracion'),
    path('guardar_valoracion/<int:clase_id>/', views.guardar_valoracion, name='guardar_valoracion'),



    path("guardar_datos_inscripcion/", views.guardar_datos_inscripcion, name="guardar_datos"),
    path("enviar_confirmacion/", views.enviar_confirmacion, name="enviar_confirmacion"),



    path('alta_alumno/', alta_alumno_view, name='alta_alumno'), # altas de alumnos manuales http://127.0.0.1:8000/alta_alumno/

    path('alta_exitosa/', alumno_alta_exitosa_view, name='alumno_alta_exitosa'),

    path('verificar-nombre-usuario/', views.verificar_nombre_usuario, name='verificar_nombre_usuario'),

    path('alta_comision/', views.alta_comision_view, name='alta_comision'), #http://127.0.0.1:8000/alta_comision/
    path('alta_clase_comision/', views.alta_clase_comision_view, name='alta_clase_comision'), #http://127.0.0.1:8000/alta_clase_comision/



    #  path('mis-cursos/', views.mis_cursos_view, name='mis_cursos'), #con este path no me anda el login

    # path('<str:id_curso>/', el_curso_view, name='curso_detalle'),
    # path('<str:id_curso>/', curso_detalle_view, name='curso_detalle'),
    path('curso/<str:id_comision>/', curso_detalle_view, name='curso_detalle'),


    # path('curso/desarrollo-web/', views.curso_desarrollo_web_view, name='curso_desarrollo_web'),


    path('participantes/', views.participantes_view, name='participantes'), #http://127.0.0.1:8000/participantes/
    # path('participantes/curso/<int:curso_id>/', views.participantes_view, name='participantes'), #http://127.0.0.1:8000/participantes/curso/02/
    path('participantes/curso/<str:curso_id>/', views.participantes_view, name='participantes'),  #http://127.0.0.1:8000/participantes/curso/01/

    path('participantes/<int:numero_comision>/<str:id_curso>/', views.participantes_view, name='participantes'),


    path('usuarios/', views.listar_usuarios_view, name='listar_usuarios'), 

    # path('marcar_presente/<int:clase_id>/', views.marcar_presente, name='marcar_presente'),
    path('marcar_presente/<str:comision_id>/<int:clase_id>/<str:alumno_id>/', views.marcar_presente, name='marcar_presente'),

    path('agradecimiento/', views.agradecimiento, name='agradecimiento'),


    # path('curso/<str:nombre_curso>/quizzes/', views.hub_de_quizzes, name='hub_de_quizzes'), #http://127.0.0.1:8000/hub_de_quizzes
    path('quiz/<int:clase_id>/', views.quiz_por_clase, name='quiz_por_clase'), 
    # path('curso/<int:curso_id>/comision/<int:comision_id>/estudiante/<str:estudiante_id>/quizzes/', views.hub_de_quizzes, name='hub_de_quizzes'),
    path('curso/<str:curso_id>/comision/<str:comision_id>/estudiante/<str:estudiante_id>/quizzes/', views.hub_de_quizzes, name='hub_de_quizzes'),



    # path('entrega-proyecto/<int:comision_id>/', views.entrega_proyecto_view, name='entrega_proyecto'),
    path('entrega-proyecto/<str:comision_id>/', views.entrega_proyecto_view, name='entrega_proyecto'),


    path("procesar_pago_mercado/", views.procesar_pago_mercado, name="procesar_pago_mercado"),

    path('proximas_comisiones/', views.proximas_comisiones_desarrollo_web, name='proximas_comisiones'),

    path('mi_certificado/', views.mi_certificado_redirect, name='mi_certificado_redirect'),
    path('mi_certificado/<str:id_estudiante>/<str:id_comision>/', views.mi_certificado, name='mi_certificado'),


    path('chat_general/', views.chat_general, name='chat_general'),
    path('chat_general/mensajes/', views.obtener_mensajes, name='obtener_mensajes'),

    path('chat_general/escribiendo/', views.obtener_typing, name='obtener_typing'),
    path('chat_general/marcar_escribiendo/', views.marcar_escribiendo, name='marcar_escribiendo'),

    path('editar_mensaje/', views.editar_mensaje, name='editar_mensaje'),
    path('borrar_mensaje/', views.borrar_mensaje, name='borrar_mensaje'),

    path('chat/toggle_destacar/', views.toggle_destacar_mensaje, name='toggle_destacar'),

    # path('comision/<str:comision_id>/entregas/', views.ver_entregas_proyectos, name='ver_entregas_proyectos'),
    path('entrega/<int:entrega_id>/guardar/', views.guardar_nota_feedback, name='guardar_nota_feedback'),

    path('curso/<str:curso_id>/comision/<str:comision_id>/entregas/', views.ver_entregas_proyectos, name='ver_entregas_proyectos'),


]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)