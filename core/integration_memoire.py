import threading

from core.continuite import reprendre_si_ia_revenue
from core.demarrage import recuperer_etat_rapide
from core.quotas import restaurer_blocages


def _trouver_routeur(jarvis):
    for valeur in getattr(jarvis, "__dict__", {}).values():
        routeur = getattr(valeur, "router", None)
        if routeur is not None:
            return routeur
    return None


def demarrer_memoire(jarvis, attente=10):
    resultat = {}
    routeur = _trouver_routeur(jarvis)

    def travail():
        try:
            repris = []
            if routeur is not None:
                restaurer_blocages(routeur)
                repris = reprendre_si_ia_revenue(routeur)
            resultat["repris"] = repris
            resultat["etat"] = recuperer_etat_rapide()
        except Exception:
            resultat["erreur"] = True

    fil = threading.Thread(target=travail, daemon=True)
    fil.start()
    fil.join(attente)
    if fil.is_alive():
        print("[Mémoire] chargement en cours (réseau lent) : "
              "démarrage sans attendre.")
        return
    if resultat.get("erreur") or "etat" not in resultat:
        print("[Mémoire] indisponible pour le moment.")
        return
    etat = resultat["etat"]
    if etat["hors_ligne"]:
        print("[Mémoire] hors ligne :", etat["en_attente"],
              "point(s) gardé(s) en local.")
        return
    for p in etat["projets"]:
        if p["derniere_action"]:
            print("[Mémoire]", p["nom"], ":", p["derniere_action"], "->",
                  p["prochaine_action"] or "-")
    for titre in resultat.get("repris", []):
        print("[Mémoire] tâche reprise (IA revenue) :", titre)
