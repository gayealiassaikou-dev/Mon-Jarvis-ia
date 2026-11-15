from marge import calculate_margin

cas = [
    ((1500, 2000, 10), (500, 5000, 33.33)),
    ((10, 15, 2), (5, 10, 50)),
    ((0, 15, 2), (15, 30, 0)),
]

ok = True
for args, attendu in cas:
    r = tuple(round(x, 2) for x in calculate_margin(*args))
    if r == attendu:
        print("OK", args, r)
    else:
        print("ECHEC", args, r, "attendu", attendu)
        ok = False

raise SystemExit(0 if ok else 1)
