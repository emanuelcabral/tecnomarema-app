# Este formulario solo se encarga de:

# Verificar el email

# Enviar el email con token para resetear


from django import forms
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

from plataforma.models import PerfilUsuario

class CustomPasswordResetForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico", max_length=254)

    def get_users(self, email):
        return PerfilUsuario.objects.filter(correo__iexact=email, is_active=True)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not self.get_users(email).exists():
            raise forms.ValidationError("No existe ningún usuario con ese correo.")
        return email

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        email = self.cleaned_data["email"]
        for user in self.get_users(email):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            protocol = 'https' if use_https else 'http'
            domain = domain_override or (request.get_host() if request else 'example.com')

            context = {
                'email': user.correo,
                'domain': domain,
                'site_name': 'Tecno Marema',
                'uid': uid,
                'user': user,
                'token': token,
                'protocol': protocol,
                **(extra_email_context or {}),
            }

            subject = render_to_string(subject_template_name, context).strip()
            body = render_to_string(email_template_name, context)

            send_mail(
                subject,
                body,
                from_email or settings.DEFAULT_FROM_EMAIL,
                [user.correo],
                fail_silently=False,
                html_message=render_to_string(html_email_template_name, context) if html_email_template_name else None,
            )

# #######################################################################################################
# ##---------------------------------subir foto al perfil----------------------------------------------##
# #######################################################################################################


from django import forms
from .models import PerfilUsuario

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['foto']
#########################################################################################################
##--------------------------------- alta manual de usuarios -------------------------------------------##
#########################################################################################################

from django import forms
from .models import PerfilUsuario
from .models import DatosDeEstudiantes

# class AltaAlumnoForm(forms.ModelForm):
#     # username = forms.CharField(max_length=150, label="Nombre de usuario")
#     username = forms.CharField(
#     max_length=150,
#     label="Nombre de usuario",
#     widget=forms.TextInput(attrs={'id': 'id_username'})
# )
#     password = forms.CharField(widget=forms.PasswordInput, label="Contraseña provisional")

#     class Meta:
#         model = DatosDeEstudiantes
#         fields = [
#             'id_estudiante', 'nombre', 'apellido', 'dni', 'correo',
#             'fecha_nacimiento', 'pais', 'provincia', 'telefono',
#             'genero', 'biografia',
#             'cursando1', 'cursando2', 'cursando3', 'cursando4',
#             'cursando5', 'cursando6', 'cursando7', 'cursando8', 'cursando9'
#         ]

# def clean_username(self):
#     username = self.cleaned_data.get('username')
#     if PerfilUsuario.objects.filter(nombre_usuario=username).exists():
#         raise forms.ValidationError("Este nombre de usuario ya está en uso. Elegí otro.")
#     return username

from django import forms
from .models import PerfilUsuario, DatosDeEstudiantes

class AltaAlumnoForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        label="Nombre de usuario",
        widget=forms.TextInput(attrs={'id': 'id_username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Contraseña provisional"
    )

    class Meta:
        model = DatosDeEstudiantes
        fields = [
            'id_estudiante', 'nombre', 'apellido', 'dni', 'correo',
            'fecha_nacimiento', 'pais', 'provincia', 'telefono',
            'genero', 'biografia',
            'cursando1', 'cursando2', 'cursando3', 'cursando4',
            'cursando5', 'cursando6', 'cursando7', 'cursando8', 'cursando9'
        ]

    # ←--- Esta función verifica si el nombre de usuario ya existe
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if PerfilUsuario.objects.filter(nombre_usuario=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso. Elegí otro.")
        return username

    # ←--- Esta función hace que el campo 'id_estudiante' se muestre solo lectura
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_estudiante'].widget.attrs['readonly'] = True



#######################################################################################
###-------------------------alta comisiones-----------------------------------------###
#######################################################################################

from .models import Comision

class ComisionForm(forms.ModelForm):
    class Meta:
        model = Comision
        fields = '__all__'
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date'}),
            'dia1': forms.TextInput(attrs={'placeholder': 'Ej: Lunes'}),
            'dia2': forms.TextInput(attrs={'placeholder': 'Ej: Miércoles'}),
            'dia3': forms.TextInput(attrs={'placeholder': 'Ej: Viernes'}),
            'horario1': forms.TextInput(attrs={'placeholder': 'Ej: 18:00 a 20:00'}),
            'horario2': forms.TextInput(attrs={'placeholder': 'Ej: 18:00 a 20:00'}),
            'horario3': forms.TextInput(attrs={'placeholder': 'Ej: 18:00 a 20:00'}),
        }


#######################################################################################
####---------------------------alta de cursos--------------------------------------####
#######################################################################################


# plataforma/forms.py
from django import forms
from .models import Curso

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        exclude = ['id_curso', 'fecha_creacion']

#--------------------------------------------------------------------------------------#
##------------------------alta clase comision------------------------------------------#
#--------------------------------------------------------------------------------------#

from django import forms
from .models import ClaseComision

class ClaseComisionForm(forms.ModelForm):
    class Meta:
        model = ClaseComision  # o el modelo que uses
        fields = ['comision', 'clase', 'fecha', 'horario', 'link', 'video']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['link'].required = False
        self.fields['video'].required = False