import sys

def calculate_margin(purchase_price: float, selling_price: float, quantity: int):
    """Calculate unit margin, total margin and margin percentage.

    Args:
        purchase_price (float): Cost price per unit.
        selling_price (float): Sale price per unit.
        quantity (int): Number of units sold.

    Returns:
        tuple: (unit_margin, total_margin, percentage)
    """
    unit_margin = selling_price - purchase_price
    total_margin = unit_margin * quantity
    percentage = (unit_margin / purchase_price) * 100 if purchase_price != 0 else 0.0
    return unit_margin, total_margin, percentage

if __name__ == "__main__":
    if len(sys.argv) == 4:
        try:
            purchase = float(sys.argv[1])
            selling = float(sys.argv[2])
            qty = int(sys.argv[3])
            unit, total, pct = calculate_margin(purchase, selling, qty)
            print(f"Marge unitaire : {unit:.2f}")
            print(f"Marge totale   : {total:.2f}")
            print(f"Pourcentage    : {pct:.2f}%")
        except ValueError:
            print("Erreur: les arguments doivent être numériques (prix et quantité).")
    else:
        print("Usage: python marge.py <prix_achat> <prix_vente> <quantité>")
        print("Exemple: python marge.py 10 15 2")
