import time
from datetime import datetime, timezone

from core.reprise import ERREURS_RESEAU, sauvegarder_point
from core.supabase_tables import SupabaseTables

MARQUE_LOCAL = "[local]"
MARQUE_ATTENTE = "attente_ia"


def _maintenant():
    return datetime.now(timezone.utc).isoformat()


def _projet_id(t, nom_projet):
    projets = t.lister("projets", nom=nom_projet)
    if not projets:
        raise ValueError("Projet inconnu : " + nom_projet)
    return projets[0]["id"]


def toutes_ia_indisponibles(router):
    noms = list(getattr(router, "fournisseurs", []))
    return bool(noms) and all(not router.disponible(n) for n in noms)


def retour_prevu(router):
    fins = [
        router.indisponibles[n]
        for n in getattr(router, "fournisseurs", [])
        if n in router.indisponibles
    ]
    return min(fins) if fins else None


def classer_taches(nom_projet):
    t = SupabaseTables()
    taches = t.lister(
        "taches", ordre="ordre.asc",
        projet_id=_projet_id(t, nom_projet), statut="a_faire",
    )
    locales = [x for x in taches if x["titre"].startswith(MARQUE_LOCAL)]
    avec_ia = [x for x in taches if not x["titre"].startswith(MARQUE_LOCAL)]
    return locales, avec_ia


def mettre_en_attente_ia(nom_projet, titre_tache, router):
    fin = retour_prevu(router)
    heure = time.strftime("%H:%M", time.localtime(fin)) if fin else "inconnue"
    mise_a_jour = True
    try:
        t = SupabaseTables()
        taches = t.lister(
            "taches", projet_id=_projet_id(t, nom_projet), titre=titre_tache
        )
        if not taches:
            raise ValueError("Tâche inconnue : " + titre_tache)
        t._requete(
            "PATCH", "taches", params={"id": "eq." + taches[0]["id"]},
            donnees={
                "statut": "bloquee", "resultat": MARQUE_ATTENTE,
                "date_modification": _maintenant(),
            },
        )
    except ERREURS_RESEAU:
        mise_a_jour = False
    sauvegarder_point(
        nom_projet, "En attente de l'IA",
        derniere_etape="tâche en pause : " + titre_tache,
        prochaine_action="Reprendre : " + titre_tache,
        blocages="Tous les fournisseurs IA sont bloqués (retour prévu vers "
        + heure + ")",
    )
    return {"heure": heure, "tache_mise_a_jour": mise_a_jour}


def reprendre_si_ia_revenue(router):
    if toutes_ia_indisponibles(router):
        return []
    repris = []
    try:
        t = SupabaseTables()
        for x in t.lister("taches", statut="bloquee", resultat=MARQUE_ATTENTE):
            t._requete(
                "PATCH", "taches", params={"id": "eq." + x["id"]},
                donnees={
                    "statut": "a_faire", "resultat": "",
                    "date_modification": _maintenant(),
                },
            )
            repris.append(x["titre"])
    except ERREURS_RESEAU:
        pass
    return repris


if __name__ == "__main__":
    print("core.continuite : fonctions toutes_ia_indisponibles, "
          "mettre_en_attente_ia, reprendre_si_ia_revenue, classer_taches")
