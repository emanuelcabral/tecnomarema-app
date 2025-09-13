# #util_filtros.py
from django import template
from datetime import datetime, timedelta

register = template.Library()

# 🔹 Acceso a diccionarios
@register.filter(name="get_item")
@register.filter(name="dict_get")
def dict_get(d, key):
    return d.get(key)

# 🔹 Resta 10 minutos a una hora en formato "HH:MM"
@register.filter
def resta_10min(hora_str):
    try:
        hora = datetime.strptime(hora_str, "%H:%M")
        nueva_hora = hora - timedelta(minutes=10)
        return nueva_hora.strftime("%H:%M")
    except:
        return hora_str

# 🔹 Suma 30 minutos a una hora en formato "HH:MM"
@register.filter
def suma_30min(hora_str):
    try:
        hora = datetime.strptime(hora_str, "%H:%M")
        nueva_hora = hora + timedelta(minutes=30)
        return nueva_hora.strftime("%H:%M")
    except:
        return hora_str

# 🔹 Agrupar lista en bloques de N elementos
@register.filter
def agrupar_por(lista, n):
    if not lista:
        return []
    n = int(n)
    return [lista[i:i + n] for i in range(0, len(lista), n)]

# 🔹 Multiplicar dos valores
@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except:
        return ''

# 🔹 Filtros para archivos / cadenas
@register.filter
def endswith(value, suffix):
    return str(value).lower().endswith(suffix.lower())

@register.filter
def startswith(value, prefix):
    return str(value).lower().startswith(prefix.lower())

@register.filter
def contains(value, substring):
    return substring.lower() in str(value).lower()

###################################################################################
# -------------------- Filtro de comisiones del estudiante -----------------------
###################################################################################

@register.filter
def comisiones_del_usuario(estudiante):
    if not estudiante:
        return []
    return [c for c in [
        estudiante.cursando1, estudiante.cursando2, estudiante.cursando3,
        estudiante.cursando4, estudiante.cursando5, estudiante.cursando6,
        estudiante.cursando7, estudiante.cursando8, estudiante.cursando9
    ] if c]

###################################################################################
# -------------------- Filtro de restas -----------------------
###################################################################################
from django import template

@register.filter
def resta(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

###################################################################################
# ---------- Filtro para reemplazar usado en las urls de cursos.html --------------
###################################################################################
from django import template

@register.filter
def replace(value, args):
    old, new = args.split(',')
    return value.replace(old, new)