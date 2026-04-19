from datetime import timedelta
from models import Feriado

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