from plataforma.models import AsistenciaClase, DatosDeEstudiantes, Clase, ClaseComision

def run():
    print("📥 Cargando asistencias...")

    filas = [
        ("000001", 1),
        ("000002", 2),
        ("000003", 3),
        ("000004", 4),
        ("000005", 5),
        ("000006", 6),
        ("000001", 7),
        ("000002", 8),
        ("000003", 9),
        ("000004", 10),
    ]

    for estudiante_id, clase_id in filas:
        try:
            estudiante = DatosDeEstudiantes.objects.get(id_estudiante=estudiante_id)
            clase = Clase.objects.get(id=clase_id)
            cc = ClaseComision.objects.filter(clase=clase).first()

            if not cc:
                print(f"⚠️ No se encontró ClaseComision para clase {clase_id}")
                continue

            if not AsistenciaClase.objects.filter(estudiante=estudiante, clase=clase).exists():
                asistencia = AsistenciaClase(
                    estudiante=estudiante,
                    clase=clase,
                    nombre=estudiante.nombre,
                    apellido=estudiante.apellido,
                    nombre_usuario=getattr(estudiante.perfilusuario, "nombre_usuario", "-"),
                    curso=clase.curso.nombre_curso if clase.curso else "-",
                    comision=str(cc.comision.numero_comision) if cc.comision else "-",
                    nombre_clase=clase.nombre_clase,
                    fecha_clase=cc.fecha,
                    horario_inicio=cc.horario,
                    horario_fin=cc.hora_fin,
                )
                asistencia.save()
                print(f"✅ Asistencia registrada: {estudiante_id} en clase {clase_id}")
            else:
                print(f"⚠️ Ya existe: {estudiante_id} en clase {clase_id}")
        except Exception as e:
            print(f"❌ Error en {estudiante_id}/{clase_id}: {e}")
