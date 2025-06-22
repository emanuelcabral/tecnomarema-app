from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


#############################################################################


from datetime import datetime, timedelta

@register.filter
def resta_10min(hora_str):
    try:
        hora = datetime.strptime(hora_str, "%H:%M")
        nueva_hora = hora - timedelta(minutes=10)
        return nueva_hora.strftime("%H:%M")
    except:
        return hora_str

@register.filter
def suma_30min(hora_str):
    try:
        hora = datetime.strptime(hora_str, "%H:%M")
        nueva_hora = hora + timedelta(minutes=30)
        return nueva_hora.strftime("%H:%M")
    except:
        return hora_str

###########################################################################

@register.filter
def agrupar_por(lista, n):
    """Divide una lista en grupos de tamaño n (seguro ante None)"""
    if not lista:
        return []
    n = int(n)
    return [lista[i:i + n] for i in range(0, len(lista), n)]
