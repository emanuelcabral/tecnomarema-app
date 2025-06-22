# from django.db import models

# # Create your models here.

# from django.db import models

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.db import models

# Manager personalizado para PerfilUsuario
class PerfilUsuarioManager(BaseUserManager):
    def create_user(self, nombre_usuario, correo, password=None, **extra_fields):
        if not nombre_usuario:
            raise ValueError('El nombre de usuario debe ser obligatorio')
        if not correo:
            raise ValueError('El correo debe ser obligatorio')
        correo = self.normalize_email(correo)
        user = self.model(nombre_usuario=nombre_usuario, correo=correo, **extra_fields)
        user.set_password(password)  # Hashea la contraseña y la guarda en el campo password
        user.save(using=self._db)
        return user

    def create_superuser(self, nombre_usuario, correo, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(nombre_usuario, correo, password, **extra_fields)

# Modelo personalizado PerfilUsuario
class PerfilUsuario(AbstractBaseUser, PermissionsMixin):
    id_usuario = models.CharField(max_length=6, primary_key=True)
    id_estudiante = models.OneToOneField('DatosDeEstudiantes', on_delete=models.CASCADE, null=True, blank=True)
    nombre_usuario = models.CharField(max_length=150, unique=True)
    correo = models.EmailField(unique=True)

    # 🔽 Campo nuevo para la foto de perfil
    foto = models.ImageField(upload_to='fotos_perfil/', blank=True, null=True)

        # 🔽 Campo nuevo para distinguir el rol del usuarioo
    rol = models.CharField(max_length=20, choices=[
        ('alumno', 'Alumno'),
        ('profesor', 'Profesor'),
        ('tutor', 'Tutor'),
    ], default='alumno') 

    @property
    def email(self):
        return self.correo


    # El campo 'password' viene por AbstractBaseUser y es visible en la tabla con hash
    # password = models.CharField(max_length=128)  # NO definir explícitamente, ya existe

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    objects = PerfilUsuarioManager()

    USERNAME_FIELD = 'nombre_usuario'
    REQUIRED_FIELDS = ['correo']

    def __str__(self):
        return self.nombre_usuario


class Curso(models.Model):
    id_curso = models.CharField(max_length=2, primary_key=True)
    nombre_curso = models.CharField(max_length=200)
    estado_curso = models.CharField(max_length=20, choices=[
        ('proximo', 'Próximo'),
        ('en_curso', '¡En curso!'),
        ('finalizado', 'Finalizado'),
    ], default='proximo')
    # fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_creacion = models.DateTimeField()
    descripcion = models.TextField()
    consigna_proyecto = models.TextField(blank=True, null=True)
    # duracion = models.CharField(blank=True, null=True)
    duracion = models.CharField(max_length=20, choices=[
        ('0.5hs', '0.5 hs'),
        ('1hs', '1 hs'),
        ('1.5hs', '1.5 hs'),
        ('2hs', '2 hs'),
        ('2.5hs', '2.5 hs'),
        ('3hs', '3 hs'),
    ], default='2hs')

    # Nuevos campos
    precio_original = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_final = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    modalidad = models.CharField(max_length=50, choices=[
        ('online_vivo', 'Online en vivo'),
        ('online_grabado', 'Online grabado'),
        ('presencial', 'Presencial'),
        ('hibrido', 'Híbrido'),
    ], default='online_vivo')


    # 🔽 Campo nuevo para la icono del curso
    icono01 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono02 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono03 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono04 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono05 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono06 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono07 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono08 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono09 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono10 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono11 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)
    icono12 = models.ImageField(upload_to='iconos_cursos/', blank=True, null=True)

    def __str__(self):
        return f"{self.nombre_curso} ({self.estado_curso})"
    
    @property
    def iconos_cargados(self):
        return [
            getattr(self, f'icono{str(i).zfill(2)}') 
            for i in range(1, 13)
            if getattr(self, f'icono{str(i).zfill(2)}')
        ]
    

# ---------------------------------------------------------------------

class Comision(models.Model):
    id_comision = models.CharField(max_length=6, primary_key=True)
    id_curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    numero_comision = models.IntegerField()
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    dia1 = models.CharField(max_length=20, blank=True, null=True)
    dia2 = models.CharField(max_length=20, blank=True, null=True)
    dia3 = models.CharField(max_length=20, blank=True, null=True)

    horario1 = models.CharField(max_length=20, blank=True, null=True)
    horario2 = models.CharField(max_length=20, blank=True, null=True)
    horario3 = models.CharField(max_length=20, blank=True, null=True)

    estado_comision = models.CharField(max_length=20, choices=[
        ('proximo', 'Próximo'),
        ('en_curso', '¡En curso!'),
        ('finalizado', 'Finalizado'),
    ], default='proximo')

    def __str__(self):
        return f"Comisión {self.numero_comision} - {self.id_curso.nombre_curso}"

# ---------------------------------------------------------------------


class DatosDeEstudiantes(models.Model):
    id_estudiante = models.CharField(max_length=6, primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20)
    correo = models.EmailField(unique=True)
    fecha_nacimiento = models.DateField()
    pais = models.CharField(max_length=100)
    provincia = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)


      # Campos nuevos
    genero = models.CharField(max_length=20, blank=True, null=True)  # ejemplo: "Masculino", "Femenino", "Otro"
    biografia = models.TextField(blank=True, null=True)  # texto libre, descripción biográfica

    cursando1 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c1')
    cursando2 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c2')
    cursando3 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c3')
    cursando4 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c4')
    cursando5 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c5')
    cursando6 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c6')
    cursando7 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c7')
    cursando8 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c8')
    cursando9 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c9')
    # cursando10 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c10')
    # cursando11 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c11')
    # cursando12 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c12')
    # cursando13 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c13')
    # cursando14 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c14')
    # cursando15 = models.ForeignKey(Comision, on_delete=models.SET_NULL, null=True, blank=True, related_name='c15')

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

########################################################################################
#--------------------------------valorar clase-----------------------------------------#
########################################################################################

# Tabla Clase
class Clase(models.Model):
    # id_clase = models.AutoField(primary_key=True)
    # curso = models.CharField(max_length=100)
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name='clases')
    # comision = models.ForeignKey('Comision', on_delete=models.CASCADE, related_name='clases_de_clase')  # ✅ Añadir esta línea
    # comision = models.IntegerField()
    numero_clase = models.IntegerField()
    nombre_clase = models.CharField(max_length=100)
    estado_clase = models.CharField(max_length=20, choices=[
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ], default='Activo')
    # fecha_clase = models.DateField(null=True, blank=True)
    ppt = models.URLField(blank=True, null=True)     #google slides

    def __str__(self):
        return f"Clase {self.numero_clase}: {self.nombre_clase}"
#-----------------------------------------------------------------------------------------------
# Tabla ValoracionAlumno
class ValoracionAlumno(models.Model):
    valoracion_alumno_id = models.AutoField(primary_key=True)

    id_estudiante = models.CharField(max_length=10)  # desde DatosDeEstudiantes
    id_usuario = models.CharField(max_length=10)     # desde PerfilUsuario

    nombre_usuario = models.CharField(max_length=50)  # desde sesión o editable por el usuario

    clase = models.ForeignKey(Clase, on_delete=models.CASCADE)

    preferencia_clase = models.CharField(
        max_length=20,
        choices=[
            ('me_gusto', 'Me gustó'),
            ('mas_o_menos', 'Más o menos'),
            ('no_me_gusto', 'No me gustó')
        ]
    )

    rol_profe = models.IntegerField()      # 1 a 10
    contenido = models.IntegerField()      # 1 a 10
    plataforma = models.IntegerField()     # 1 a 10
    streaming = models.IntegerField()      # 1 a 10
    comentarios = models.TextField(blank=True, null=True)

    fecha_valoracion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Valoración de {self.nombre_usuario} para Clase {self.clase.numero_clase}"
    
#######################################################################################################################################
#------------------------La nueva tabla ClaseComision (detalla las variaciones de datos en diferentes comisiones)------------------####
#######################################################################################################################################

from django.db import models

class ClaseComision(models.Model):
    clase = models.ForeignKey('Clase', on_delete=models.CASCADE, related_name='instancias')
    comision = models.ForeignKey('Comision', on_delete=models.CASCADE, related_name='clases')
    perfil_usuario = models.ForeignKey('PerfilUsuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='clases_dictadas')  # profesor o tutor asignado a la clase

    ### Info personalizada por comisión y clase ###
    fecha = models.DateField(null=True, blank=True)
    horario = models.TimeField(null=True, blank=True)  # Solo hora y minuto, segundos siempre 00
    hora_fin = models.TimeField(null=True, blank=True)
    link = models.URLField(blank=True, null=True)     # Link a plataforma (Jitsi, Zoom, etc.)
    video = models.URLField(blank=True, null=True)    # Grabación posterior a la clase

    def __str__(self):
        return f"{self.clase.nombre_clase} - {self.comision} - {self.fecha} {self.horario.strftime('%H:%M') if self.horario else 'Horario no definido'}"
    
####################################################################################################################
#----------------------------------------modelo de asistencias generales-------------------------------------------#
####################################################################################################################
from django.db import models
from django.utils import timezone

class AsistenciaClase(models.Model):
    estudiante = models.ForeignKey('DatosDeEstudiantes', on_delete=models.CASCADE)
    clase = models.ForeignKey('Clase', on_delete=models.CASCADE)
    fecha_marcada = models.DateTimeField(auto_now_add=True)

    # Nuevos campos
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    nombre_usuario = models.CharField(max_length=150)
    curso = models.CharField(max_length=200)
    comision = models.CharField(max_length=10)
    nombre_clase = models.CharField(max_length=200)
    fecha_clase = models.DateField()
    horario_inicio = models.TimeField()
    horario_fin = models.TimeField()

    class Meta:
        unique_together = ('estudiante', 'clase')

    def __str__(self):
        return f"{self.nombre} {self.apellido} - Clase {self.nombre_clase} - Presente"

    def guardar_detalles(self):
        self.nombre = self.estudiante.nombre
        self.apellido = self.estudiante.apellido
        self.nombre_usuario = getattr(self.estudiante.perfilusuario, "nombre_usuario", "-")
        self.curso = self.clase.curso.nombre_curso if self.clase.curso else "-"
        self.nombre_clase = self.clase.nombre_clase

        from plataforma.models import ClaseComision
        cc = ClaseComision.objects.filter(clase=self.clase).first()
        if cc:
            self.comision = str(cc.comision.numero_comision) if cc.comision else "-"
            self.fecha_clase = cc.fecha
            self.horario_inicio = cc.horario
            self.horario_fin = cc.hora_fin
        else:
            self.comision = "-"
            self.fecha_clase = timezone.now().date()
            self.horario_inicio = timezone.now().time()
            self.horario_fin = timezone.now().time()

    def save(self, *args, **kwargs):
        self.guardar_detalles()
        super().save(*args, **kwargs)


# fin del codigo 


######################################################################################################
###----------------------------------preguntas del quizze------------------------------------------###
######################################################################################################

from django.db import models
from .models import Clase  # Asegurate de tener importado Clase

class Pregunta(models.Model):
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE)
    texto = models.TextField()
    opcion_a = models.CharField(max_length=255)
    opcion_b = models.CharField(max_length=255)
    opcion_c = models.CharField(max_length=255)
    opcion_d = models.CharField(max_length=255)
    respuesta_correcta = models.CharField(max_length=1, choices=[
        ('a', 'Opción A'),
        ('b', 'Opción B'),
        ('c', 'Opción C'),
        ('d', 'Opción D')
    ])

    def __str__(self):
        return f"[Clase {self.clase.numero_clase}] {self.texto[:50]}"

#------------------------------------------------------------------------
from django.db import models

class PuntajeQuiz(models.Model):
    estudiante = models.ForeignKey('DatosDeEstudiantes', on_delete=models.CASCADE)
    clase = models.ForeignKey('Clase', on_delete=models.CASCADE)
    puntaje_inicial = models.IntegerField(default=0)
    puntaje_maximo = models.IntegerField(default=0)

    class Meta:
        unique_together = ('estudiante', 'clase')


#####################################################################################
####-----------------------Entrega del Proyecto Final----------------------------####
#####################################################################################

from django.db import models
from django.utils import timezone

class EntregaProyecto(models.Model):
    estudiante = models.ForeignKey("DatosDeEstudiantes", on_delete=models.CASCADE)
    curso = models.ForeignKey("Curso", on_delete=models.CASCADE)
    comision = models.ForeignKey("Comision", on_delete=models.CASCADE)

    titulo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)

    # Enlaces
    link_github = models.URLField(blank=True, null=True)
    link_pages = models.URLField(blank=True, null=True)
    link_servidor = models.URLField(blank=True, null=True)
    link_adicional = models.URLField(blank=True, null=True)

    # Archivos opcionales
    archivo_1 = models.FileField(upload_to='entregas/', blank=True, null=True)
    archivo_2 = models.FileField(upload_to='entregas/', blank=True, null=True)
    archivo_3 = models.FileField(upload_to='entregas/', blank=True, null=True)

    # Multimedia
    imagen = models.ImageField(upload_to='entregas/imagenes/', blank=True, null=True)
    video = models.FileField(upload_to='entregas/videos/', blank=True, null=True)
    audio = models.FileField(upload_to='entregas/audios/', blank=True, null=True)

    comentarios_adicionales = models.TextField(blank=True, null=True)

    fecha_entrega = models.DateTimeField(default=timezone.now)

    nota = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('estudiante', 'comision')  # ✅ No se puede repetir la entrega por alumno y comisión

    def __str__(self):
        return f"{self.estudiante} - {self.curso.nombre_curso} - Proyecto"
