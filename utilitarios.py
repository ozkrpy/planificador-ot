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