from datetime import timedelta, date, datetime
import re
from dateutil.relativedelta import relativedelta


MESES_ES = {
    "ene": "Jan", "feb": "Feb", "mar": "Mar", "abr": "Apr",
    "may": "May", "jun": "Jun", "jul": "Jul", "ago": "Aug",
    "sep": "Sep", "oct": "Oct", "nov": "Nov", "dic": "Dec",
}

def convertir_fecha(fecha):
    try:
        dt = datetime.strptime(fecha, "%d %b %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(_normalizar_mes(fecha), "%d %b %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return convertir_fecha_relativa(fecha)


def convertir_fecha_relativa(texto_fecha):
    hoy = datetime.now()
    if 'MINUTO' in texto_fecha.upper() or 'HORA' in texto_fecha.upper():
        minutos = int(re.search(r'\d+', texto_fecha).group())
        return (hoy-timedelta(minutes=minutos)).strftime("%Y-%m-%d")
    elif 'HORA' in texto_fecha.upper():
        return
    elif 'DÍA' in texto_fecha.upper() or 'DIA' in texto_fecha.upper():
        try:
            dias = int(re.search(r'\d+', texto_fecha).group())
            return (hoy - timedelta(days=dias)).strftime("%Y-%m-%d")
        except:
            if 'UN' in texto_fecha.upper() or '1' in texto_fecha.upper():
                return (hoy - timedelta(days=1)).strftime("%Y-%m-%d")
            return texto_fecha
    elif 'SEMANA' in texto_fecha.upper():
        try:
            semanas = int(re.search(r'\d+', texto_fecha).group())
            return (hoy - timedelta(weeks=semanas)).strftime("%Y-%m-%d")
        except:
            return texto_fecha
    elif 'MES' in texto_fecha.upper():
        try:
            meses = int(re.search(r'\d+', texto_fecha).group())
            return (hoy - relativedelta(months=meses)).strftime("%Y-%m-%d")
        except:
            if 'UN' in texto_fecha.upper() or '1' in texto_fecha.upper():
                return (hoy - relativedelta(months=1)).strftime("%Y-%m-%d")
            return texto_fecha
    else:
        return texto_fecha
    

def _normalizar_mes(fecha: str) -> str:
    """Replace Spanish month abbreviation with English equivalent."""
    partes = fecha.split()
    return " ".join(MESES_ES.get(p.lower(), p) for p in partes)