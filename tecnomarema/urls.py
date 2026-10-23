# tecnomarema/urls.py

from django.contrib import admin
from django.urls import path, include
from django.core.exceptions import PermissionDenied, SuspiciousOperation


# ---------- VISTAS DE PRUEBA (TEMPORALES) ----------
def test_400(request):
    raise SuspiciousOperation("Prueba 400")

def test_403(request):
    raise PermissionDenied("Prueba 403")

def test_500(request):
    raise Exception("Prueba 500")


urlpatterns = [
    path('admin/', admin.site.urls),

    # Rutas de prueba: BORRAR cuando termines de testear
    path('test-400/', test_400),
    path('test-403/', test_403),
    path('test-500/', test_500),

    path('', include('plataforma.urls')),
]

# Handlers de error (tienen que estar en el urls.py raíz)
handler400 = 'plataforma.views.error_400_view'
handler403 = 'plataforma.views.error_403_view'
handler404 = 'plataforma.views.error_404_view'
handler500 = 'plataforma.views.error_500_view'