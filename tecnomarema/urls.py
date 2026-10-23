"""
URL configuration for tecnomarema project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# from django.contrib import admin
# from django.urls import path, include     #👈 agregá esta línea

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('', include('plataforma.urls')),  # 👈 agregá esta línea
# ]


# tecnomarema/urls.py

from django.contrib import admin
from django.urls import path, include  # 👈 importante: importar include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('plataforma.urls')),  # 👈 conecta la app plataforma a la raíz
]

# Handlers de error (tienen que estar en el urls.py raíz)
handler400 = 'plataforma.views.error_400_view'
handler403 = 'plataforma.views.error_403_view'
handler404 = 'plataforma.views.error_404_view'
handler500 = 'plataforma.views.error_500_view'