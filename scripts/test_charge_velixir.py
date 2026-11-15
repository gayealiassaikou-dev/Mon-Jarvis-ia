"""Test de charge Velixir - usage manuel."""
import time
import sys
import urllib.request

URL_DEFAUT = "https://samsarr.velixir.run/health"
N_DEFAUT = 20

url = sys.argv[1] if len(sys.argv) > 1 else URL_DEFAUT
n = int(sys.argv[2]) if len(sys.argv) > 2 else N_DEFAUT

succes = 0
erreurs = 0
latences = []

print(f"Test charge {n} requetes sur {url}")
t_total = time.time()

for i in range(n):
    t = time.time()
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            lat = time.time() - t
            latences.append(lat)
            if r.status == 200:
                succes += 1
            else:
                erreurs += 1
    except Exception as e:
        erreurs += 1
        lat = time.time() - t
        latences.append(lat)

duree = time.time() - t_total

if latences:
    ls = sorted(latences)
    n_lat = len(ls)
    p50 = ls[n_lat // 2]
    p95 = ls[int(n_lat * 0.95)] if n_lat >= 20 else ls[-1]
    moy = sum(ls) / n_lat
    print(f"\nSucces: {succes}/{n} | Erreurs: {erreurs}/{n}")
    print(f"Duree totale: {duree:.2f}s")
    print(f"P50: {p50*1000:.0f}ms | P95: {p95*1000:.0f}ms | Moyenne: {moy*1000:.0f}ms")
    if succes == n:
        print("=== OK ===")
    elif succes >= n * 0.95:
        print(f"=== ACCEPTABLE ({succes}/{n}) ===")
    else:
        print(f"=== PROBLEME ({succes}/{n}) ===")
