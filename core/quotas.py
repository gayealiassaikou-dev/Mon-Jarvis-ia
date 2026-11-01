import time
from datetime import datetime, timedelta, timezone

from core.supabase_tables import SupabaseTables


def _ecrire(fournisseur, corps):
    try:
        t = SupabaseTables()
        existants = t.lister("quotas_fournisseurs", fournisseur=fournisseur)
        if existants:
            t._requete(
                "PATCH", "quotas_fournisseurs",
                params={"id": f"eq.{existants[0]['id']}"}, donnees=corps,
            )
        else:
            t._inserer("quotas_fournisseurs", dict(corps, fournisseur=fournisseur))
        return True
    except Exception:
        return False


def marquer_bloque(fournisseur, erreur="", secondes=300):
    maintenant = datetime.now(timezone.utc)
    texte = (erreur or "").lower()
    epuise = any(c in texte for c in ("402", "429", "quota"))
    return _ecrire(fournisseur, {
        "statut": "quota_epuise" if epuise else "bloque",
        "date_blocage": maintenant.isoformat(),
        "date_reinitialisation": (maintenant + timedelta(seconds=secondes)).isoformat(),
        "derniere_erreur": (erreur or "")[:300],
        "date_modification": maintenant.isoformat(),
    })


def marquer_disponible(fournisseur):
    return _ecrire(fournisseur, {
        "statut": "disponible",
        "date_blocage": None,
        "date_reinitialisation": None,
        "date_modification": datetime.now(timezone.utc).isoformat(),
    })


def bloques_actuels():
    try:
        lignes = SupabaseTables().lister("quotas_fournisseurs")
    except Exception:
        return {}
    maintenant = time.time()
    resultat = {}
    for ligne in lignes:
        fin = ligne.get("date_reinitialisation")
        if ligne.get("statut") == "disponible" or not fin:
            continue
        try:
            instant = datetime.fromisoformat(fin.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if instant > maintenant:
            resultat[ligne["fournisseur"]] = instant
    return resultat


def restaurer_blocages(router):
    restaures = []
    for fournisseur, fin in bloques_actuels().items():
        if fin > router.indisponibles.get(fournisseur, 0):
            router.indisponibles[fournisseur] = fin
            restaures.append(fournisseur)
    return restaures


if __name__ == "__main__":
    bloques = bloques_actuels()
    if not bloques:
        print("aucun fournisseur bloqué")
    for nom, fin in bloques.items():
        print(nom, "bloqué jusqu'à", time.strftime("%H:%M:%S", time.localtime(fin)))
