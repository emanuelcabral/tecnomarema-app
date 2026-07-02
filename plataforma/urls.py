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

from django.views.generic import RedirectView


from django.http import HttpResponse


from django.urls import re_path
from django.views.static import serve

def test(request):
    return HttpResponse("Django OK")

urlpatterns = [
    # ---------- PÚBLICAS ----------
    path('', views.inicio, name='inicio'),  # Página de inicio - http://127.0.0.1:8000/
    # path('home/', views.home, name='home'),  # Página principal - http://127.0.0.1:8000/home/
    path('login/', views.login_view, name='login'),  # Login de usuario - http://127.0.0.1:8000/login/
    path('logout/', LogoutView.as_view(), name='logout'),  # Cerrar sesión - http://127.0.0.1:8000/logout/
    # path('logout/', LogoutView.as_view(next_page='login'), name='logout'),  # Cerrar sesión con redirección

    path('inscripcion/', views.inscripcion, name='inscripcion'),  # Registro o inscripción - http://127.0.0.1:8000/inscripcion/
    path('cursos/', views.cursos_view, name='cursos'),  # Listado de cursos - http://127.0.0.1:8000/cursos/
    path('desarrollo_web_compra/', views.desarrollo_web_compra, name='desarrollo_web_compra'),  # Compra de curso - http://127.0.0.1:8000/desarrollo_web_compra/
    path('inteligencia_artificial_compra/', views.inteligencia_artificial_compra, name='inteligencia_artificial_compra'),  # Compra de curso - http://127.0.0.1:8000/inteligencia_artificial_compra/
    # === NUEVAS URLs para IA Promo ===
    path('inscripcion_ia_promo/', views.inscripcion_ia_promo, name='inscripcion_ia_promo'),
    path('guardar_inscripcion_ia_promo/', views.guardar_inscripcion_ia_promo, name='guardar_inscripcion_ia_promo'),
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

    path('alta_curso/', views.alta_curso_view, name='alta_curso'),


    path('administrador/admin_panel/', views.admin_panel_view, name='admin_panel'), #http://127.0.0.1:8000/admin-panel/

    path('administrador/alumnos/', views.listado_alumnos_view, name='listado_alumnos'),
    path('administrador/cursos/', views.listado_cursos_view, name='listado_cursos'),
    path('administrador/comisiones/', views.listado_comisiones_view, name='listado_comisiones'),
    path('administrador/clases/', views.listado_clases_view, name='listado_clases'),
    path('administrador/profesores/', views.listado_profesores_view, name='listado_profesores'),
    path('administrador/tutores/', views.listado_tutores_view, name='listado_tutores'),
    path('administrador/admins/', views.listado_admins_view, name='listado_admins'),


    path("administrador/chat/", views.chat_estadisticas, name="chat_estadisticas"),



    path('administrador/chat/', views.vista_chat_view, name='vista_chat'),


    path('administrador/chat/ver-mensajes-comision/<str:comision_id>/',  views.ver_mensajes_comision, name='ver_mensajes_comision'),
    path('administrador/chat/ver-mensajes/<str:usuario_id>/',  views.ver_mensajes_usuario, name='ver_mensajes_usuario'),

    path('administrador/mensajes/ver-general/', views.ver_mensajes_general, name='ver_mensajes_general'),

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

    # path('chat_general/escribiendo/', views.obtener_typing, name='obtener_typing'),
    # path('chat_general/marcar_escribiendo/', views.marcar_escribiendo, name='marcar_escribiendo'),

    path('editar_mensaje/', views.editar_mensaje, name='editar_mensaje'),
    path('borrar_mensaje/', views.borrar_mensaje, name='borrar_mensaje'),

    path('chat/toggle_destacar/', views.toggle_destacar_mensaje, name='toggle_destacar'),

    path('chat_comision/<str:id_comision>/', views.chat_comision_view, name='chat_comision'), # chat de comisiones

    path('chat_comision/<str:id_comision>/mensajes/', views.obtener_mensajes_comision, name='obtener_mensajes_comision'), # mensajes de chat por comision

    path('chat_general/enviar/', views.enviar_mensaje_general, name='enviar_mensaje_general'),
path('chat_comision/<str:id_comision>/enviar/', views.enviar_mensaje_comision, name='enviar_mensaje_comision'),
path("chat/privado/enviar/<str:id_usuario>/", views.enviar_mensaje_privado, name="enviar_mensaje_privado"),

    path('chat/buscar_usuarios/', views.buscar_usuarios, name='buscar_usuarios'),
    # path('mensaje/enviar/<str:nombre_usuario>/', views.enviar_mensaje_view, name='enviar_mensaje'),
    # path('chat/privado/<str:usuario_destino>/', views.chat_privado_view, name='chat_privado'),
    path('chat/privado/<str:nombre_usuario_destino>/', views.chat_privado, name='chat_privado'),

    path("chat_privado/<int:id>/mensajes/", views.obtener_mensajes_privado, name="chat_privado_mensajes"),





path("chat/escribiendo/", views.notificar_escribiendo, name="notificar_escribiendo"),
path("chat/verificar_escribiendo/", views.verificar_escribiendo, name="verificar_escribiendo"),



    # path('comision/<str:comision_id>/entregas/', views.ver_entregas_proyectos, name='ver_entregas_proyectos'),
    path('entrega/<int:entrega_id>/guardar/', views.guardar_nota_feedback, name='guardar_nota_feedback'),

    path('curso/<str:curso_id>/comision/<str:comision_id>/entregas/', views.ver_entregas_proyectos, name='ver_entregas_proyectos'),


    path('inscripcion_clase1/', views.formulario_inscripcion, name='formulario_inscripcion'),
    path('guardar_inscripcion/', views.guardar_inscripcion, name='guardar_inscripcion'),

    path('eliminar_cuenta/', views.eliminar_cuenta, name='eliminar_cuenta'),
    path('despedida/', views.despedida_view, name='despedida'),


path('ajax/comisiones/<str:id_curso>/', views.obtener_comisiones_por_curso, name='ajax_comisiones'),


path('ajax/obtener_clases_de_comision/', views.obtener_clases_de_comision, name='obtener_clases_de_comision'),
path('ajax/obtener_datos_clase_comision/', views.obtener_datos_clase_comision, name='obtener_datos_clase_comision'),




    path('api/estadisticas_valoracion/', views.obtener_estadisticas_valoraciones, name='estadisticas_valoracion'),

    # path('api/clases_opciones/', views.obtener_clases_opciones, name='clases_opciones'),  # comentado

    path('api/listado_cursos/', views.listado_cursos_view, name='listado_cursos'),

    # path('api/listado_comisiones/', views.obtener_comisiones, name='listado_comisiones'),  # comentado
    path('api/listado_comisiones/', views.listado_comisiones_view, name='listado_comisiones'),

    path('api/listado_clases/', views.listado_clases_view, name='listado_clases'),

    path('api/alumnos_clase1/', views.alumnos_clase1_html, name='alumnos_clase1'),





    path('alta_clases_de_curso/', views.alta_clases_de_curso, name='alta_clases_de_curso'),
    path('ajax/obtener_clases_de_curso/', views.ajax_obtener_clases_de_curso, name='ajax_obtener_clases_de_curso'),
    path('ajax/obtener_datos_clase/', views.ajax_obtener_datos_clase, name='ajax_obtener_datos_clase'),
    path('ajax/eliminar_clase/', views.ajax_eliminar_clase, name='ajax_eliminar_clase'),


    path('listado_valoraciones/', views.listado_valoraciones, name='listado_valoraciones'),

    path('listado_proyectos/', views.listado_proyectos, name='listado_proyectos'),
    path('listado_pagos/', views.listado_pagos, name='listado_pagos'),



path('guardar_datos_inscripcion_paga/', views.guardar_datos_inscripcion_paga, name='guardar_datos_inscripcion_paga'),


# En plataforma/urls.py
path('<slug:nombre_curso>_compra/', views.curso_compra_view, name='curso_compra'),


path('newsletter/', views.newsletter_view, name='newsletter'),


path('crear_preferencia/', views.crear_preferencia, name='crear_preferencia'),



path('verificar_nombre_usuario/', views.verificar_nombre_usuario, name='verificar_nombre_usuario'),

path('administrador/pagos/actualizar/<int:pago_id>/', views.actualizar_pago, name='actualizar_pago'),

# path('comisiones/<int:comision_id>/asistencia_general/', views.asistencia_general_view, name='asistencia_general'),
path('comisiones/<str:comision_id>/asistencia_general/', views.asistencia_general_view, name='asistencia_general'),

path('listado_asistencias/', views.listado_asistencias_view, name='listado_asistencias'),

# path('asistencia/estudiante/<str:estudiante_id>/comision/<int:comision_id>/', views.mi_asistencia_estudiante, name='mi_asistencia'),
path('asignar_pago_gratis/', views.asignar_pago_gratis, name='asignar_pago_gratis'),

path('enviar_correos_clase1/', views.enviar_correos_clase1, name='enviar_correos_clase1'),


path('administrador/alta_quiz/', views.alta_quiz_view, name='alta_quiz'),

# path('calendario/<int:comision_id>/', views.calendario_view, name='calendario_clases'),
path('calendario/<str:comision_id>/', views.calendario_view, name='calendario_clases'),

path('crear-clases/', views.crear_clases_comision_view, name='crear_clases_comision'),

path('administrador/envio-newsletter/', views.envio_y_edicion_de_newsletter, name='envio-newsletter'),

path('promo-desarrollo-web/', views.promo_desarrolloweb, name='promo_desarrolloweb'), #http://127.0.0.1:8000/promo-desarrollo-web/

path('validar_cupon/', views.validar_cupon, name='validar_cupon'),

# En urls.py (agregar a urlpatterns)
path('alta_y_edicion_cupones/', views.alta_y_edicion_cupones, name='alta_y_edicion_cupones'),
path('alta_y_edicion_cupones/<str:codigo>/', views.alta_y_edicion_cupones, name='alta_y_edicion_cupones_edit'),

path('login_autocompletar/', views.login_autocompletar, name='login_autocompletar'),


path('robots.txt', RedirectView.as_view(url=os.path.join(settings.STATIC_URL, 'txt/robots.txt'))),

path('mensajes_nuevos/', views.mensajes_nuevos_view, name='mensajes_nuevos'),

path("guardar-certificado/", views.guardar_certificado,   name="guardar_certificado"),

path("test/", test),


    path('api/cursos_estadisticas/', views.api_cursos_estadisticas, name='api_cursos_estadisticas'),
    path('api/comisiones_estadisticas/', views.api_comisiones_estadisticas, name='api_comisiones_estadisticas'),
    path('api/clases_estadisticas/', views.api_clases_estadisticas, name='api_clases_estadisticas'),


    path("comisiones/editar/", views.editar_comision, name="editar_comision"),
    path("comisiones/eliminar/", views.eliminar_comision, name="eliminar_comision"),

    path("alumnos/editar/", views.editar_alumno, name="editar_alumno"),
    path("alumnos/eliminar/", views.eliminar_alumno, name="eliminar_alumno"),

    path("administrador/profesores/editar/", views.editar_profesor, name="editar_profesor"),
    path("administrador/profesores/eliminar/", views.eliminar_profesor, name="eliminar_profesor"),

    path("administrador/tutores/editar/", views.editar_tutor, name="editar_tutor"),
    path("administrador/tutores/eliminar/", views.eliminar_tutor, name="eliminar_tutor"),

    path("administrador/admins/editar/", views.editar_admin, name="editar_admin"),
    path("administrador/admins/eliminar/", views.eliminar_admin, name="eliminar_admin"),

    path("administrador/valoraciones/eliminar/", views.eliminar_valoracion, name="eliminar_valoracion"),

    path("administrador/cupones/", views.listado_cupones, name="listado_cupones"),
    path("administrador/cupones/editar/", views.editar_cupon, name="editar_cupon"),
    path("administrador/cupones/eliminar/", views.eliminar_cupon, name="eliminar_cupon"),

    path("administrador/newsletters/", views.listado_newsletters, name="listado_newsletters"),
    path("administrador/newsletters/editar/", views.editar_newsletter, name="editar_newsletter"),
    path("administrador/newsletters/eliminar/", views.eliminar_newsletter, name="eliminar_newsletter"),

    path('mensajes-chat/', views.mensaje_chat_list, name='mensaje_chat_list'),
    path('mensajes-chat/eliminar/', views.eliminar_mensajes_chat, name='eliminar_mensajes_chat'),

]

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# if settings.DEBUG is False:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Sirve media incluso con DEBUG=False (hack funcional en Railway)
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]

# Al final del archivo urls.py del proyecto
handler400 = 'plataforma.views.error_400_view'
handler403 = 'plataforma.views.error_403_view'
handler404 = 'plataforma.views.error_404_view'
handler500 = 'plataforma.views.error_500_view'




# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)