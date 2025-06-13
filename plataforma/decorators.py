from django.shortcuts import redirect
from django.contrib import messages

def session_required(view_func):
    def wrapper(request, *args, **kwargs):
        if 'usuario_logueado' not in request.session:
            messages.error(request, 'Tenés que iniciar sesión para entrar acá.')
            return redirect('login')  # Nombre de la URL de login
        return view_func(request, *args, **kwargs)
    return wrapper
