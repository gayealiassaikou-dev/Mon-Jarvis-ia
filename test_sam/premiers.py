def est_premier(limit):
    """Affiche tous les nombres premiers jusqu'à `limit` (inclus)."""
    for n in range(2, limit + 1):
        # Vérifie la primalité de n
        is_prime = True
        for i in range(2, int(n ** 0.5) + 1):
            if n % i == 0:
                is_prime = False
                break
        if is_prime:
            print(n)

if __name__ == "__main__":
    est_premier(50)
