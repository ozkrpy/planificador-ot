from datetime import timedelta
from models import Feriado
from collections import defaultdict

def agrupar_por_semana(visitas):
    """
    Organiza una lista de visitas en un diccionario donde la clave es el rango
    de la semana (Lunes a Domingo) y el valor es la lista de visitas.
    """
    semanas = defaultdict(list)
    for v in visitas:
        # v.fecha.weekday() devuelve 0 para Lunes, 6 para Domingo
        inicio_semana = v.fecha - timedelta(days=v.fecha.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        
        # Etiqueta profesional para la sección
        label = f"SEMANA DEL {inicio_semana.strftime('%d/%m')} AL {fin_semana.strftime('%d/%m')}"
        semanas[label].append(v)
    
    # Ordenamos las semanas cronológicamente por la fecha de la primera visita
    return sorted(semanas.items(), key=lambda x: x[1][0].fecha)

def calcular_total(cantidad, precio_unitario):
    """Calculates total price based on quantity and unit price."""
    try:
        return float(cantidad) * float(precio_unitario)
    except (ValueError, TypeError):
        return 0.0

def formatear_para_ledger(entry):
    """Formats an entry with tabs for your specific ledger requirements."""
    # Code, Description, %, Quantity, Unit Price, Total Price
    return f"{entry.code}\t{entry.description}\t\t{entry.quantity}\t{entry.unit_price}\t{entry.total_price}"

def calcular_proximo_dia(fecha_base, dia_semana_objetivo):
    """
    fecha_base: desde cuándo empezamos a contar (usualmente date.today())
    dia_semana_objetivo: 0 para Lunes, 5 para Sábado
    """
    # 1. Hallar la siguiente ocurrencia del día de la semana
    dias_de_diferencia = (dia_semana_objetivo - fecha_base.weekday() + 7) % 7
    if dias_de_diferencia == 0: # Si es hoy, programar para la próxima semana
        dias_de_diferencia = 7
        
    fecha_candidata = fecha_base + timedelta(days=dias_de_diferencia)
    
    # 2. Validar contra Feriados y Domingos
    # Si no es laboral, saltar al día siguiente hasta encontrar uno válido
    while not Feriado.es_laboral(fecha_candidata):
        fecha_candidata += timedelta(days=1)
        
    return fecha_candidata