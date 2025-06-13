from .models import PerfilUsuario

def nombre_usuario(request):
    usuario_id = request.session.get('usuario_logueado')
    if usuario_id:
        try:
            usuario = PerfilUsuario.objects.get(id_usuario=usuario_id)
            return {'nombre_usuario': usuario.nombre}
        except PerfilUsuario.DoesNotExist:
            pass
    return {}