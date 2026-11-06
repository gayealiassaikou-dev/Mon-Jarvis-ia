def est_premier(n: int) -> bool:
    """Retourne True si n est un nombre premier, sinon False."""
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True


def afficher_premiers(limit: int = 50) -> None:
    """Affiche tous les nombres premiers de 2 à limit (inclus)."""
    for nombre in range(2, limit + 1):
        if est_premier(nombre):
            print(nombre)


if __name__ == "__main__":
    afficher_premiers(50)
