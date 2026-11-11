import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

PLANTILLAS_DIR = Path(__file__).resolve().parent / 'contratos_templates'
PLANTILLAS = {
    'profesor': 'contrato_docente.docx',
    'tutor': 'contrato_tutor.docx',
}

MARCADORES = {
    '[Nombre del Profesor/a]': 'nombre',
    '[Nombre del Tutor/a]': 'nombre',
    '[Nombre del Curso]': 'curso',
    '[Número de Comisión]': 'comision',
    '[Días de cursada]': 'dias',
    '[Horario]': 'horario',
    '[Fecha de inicio]': 'inicio',
    '[Fecha de finalización]': 'fin',
    '[Número de clases]': 'clases',
    '[Monto total]': 'monto_total',
    '[Monto por hora]': 'monto_hora',
    '[Nombre completo]': 'nombre',
    '[DNI]': 'dni',
}


class PdfNoDisponible(Exception):
    pass


def generar_docx(rol, datos):
    ruta = PLANTILLAS_DIR / PLANTILLAS[rol]
    salida = BytesIO()
    with zipfile.ZipFile(ruta) as zin, zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            contenido = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                xml = contenido.decode('utf-8')
                for marcador, clave in MARCADORES.items():
                    xml = xml.replace(marcador, escape(str(datos.get(clave, '') or '')))
                contenido = xml.encode('utf-8')
            zout.writestr(item, contenido)
    return salida.getvalue()


def pdf_disponible():
    return bool(shutil.which('soffice') or shutil.which('libreoffice'))


def docx_a_pdf(docx_bytes):
    exe = shutil.which('soffice') or shutil.which('libreoffice')
    if not exe:
        raise PdfNoDisponible('LibreOffice no está instalado en el servidor.')
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        origen = tmp / 'contrato.docx'
        origen.write_bytes(docx_bytes)
        subprocess.run(
            [exe, f'-env:UserInstallation={(tmp / "perfil").as_uri()}',
             '--headless', '--convert-to', 'pdf', '--outdir', str(tmp), str(origen)],
            check=True, timeout=120, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return (tmp / 'contrato.pdf').read_bytes()


def obtener_archivo(rol, datos, formato, cache_dir):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # La clave incluye el contenido del Word: si cambiás la plantilla, se regenera solo.
    plantilla = (PLANTILLAS_DIR / PLANTILLAS[rol]).read_bytes()
    clave = hashlib.sha1(
        plantilla + json.dumps([rol, datos], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    destino = cache_dir / f'{clave}.{formato}'
    if destino.exists():
        return destino.read_bytes()

    docx = generar_docx(rol, datos)
    contenido = docx if formato == 'docx' else docx_a_pdf(docx)
    destino.write_bytes(contenido)
    return contenido