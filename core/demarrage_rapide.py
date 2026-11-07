"""
Version rapide du démarrage qui limite le nombre de requêtes Supabase à trois :

1. Récupère les projets en cours.
2. Récupère, en une seule requête, tous les points de reprise des projets
   précédemment obtenus, triés par date de création décroissante, puis garde
   le plus récent de chaque projet.
3. Récupère, en une seule requête, toutes les tâches dont le statut est
   « a_faire », puis compte celles qui appartiennent à chaque projet.

Le comportement et le format de sortie sont identiques à
`core/demarrage.py`.
"""

from core.reprise import ERREURS_RESEAU, _lire_attente, vider_file_attente
from core.supabase_tables import SupabaseTables


def recuperer_etat_rapide():
    """Récupère l'état des projets avec trois requêtes Supabase maximum."""
    etat = {
        "envoyes": 0,
        "en_attente": len(_lire_attente()),
        "projets": [],
        "hors_ligne": False,
    }
    try:
        # 1. Nombre d'éléments déjà envoyés / en attente
        etat["envoyes"], etat["en_attente"] = vider_file_attente()

        t = SupabaseTables()

        # ------------------------------------------------------------
        # 2. Projets en cours
        # ------------------------------------------------------------
        projets = t.lister("projets", statut="en_cours")
        ids_projets = [p["id"] for p in projets]

        # ------------------------------------------------------------
        # 3. Derniers points de reprise (une seule requête)
        # ------------------------------------------------------------
        if ids_projets:
            ids_str = ",".join(map(str, ids_projets))
            points = t._requete(
                "GET",
                "points_reprise",
                params={
                    "projet_id": f"in.({ids_str})",
                    "order": "date_creation.desc",
                },
            )
        else:
            points = []

        # Conserver le point le plus récent pour chaque projet
        derniers_points = {}
        for point in points:
            pid = point.get("projet_id")
            if pid not in derniers_points:
                derniers_points[pid] = point

        # ------------------------------------------------------------
        # 4. Tâches à faire (une seule requête)
        # ------------------------------------------------------------
        taches = t._requete(
            "GET",
            "taches",
            params={"statut": "eq.a_faire", "order": "id.asc"},
        )
        compteurs = {}
        for tache in taches:
            pid = tache.get("projet_id")
            if pid in ids_projets:
                compteurs[pid] = compteurs.get(pid, 0) + 1

        # ------------------------------------------------------------
        # 5. Construction du résultat
        # ------------------------------------------------------------
        for p in projets:
            pid = p["id"]
            point = derniers_points.get(pid)
            etat["projets"].append(
                {
                    "nom": p["nom"],
                    "derniere_action": point.get("derniere_action")
                    if point
                    else None,
                    "prochaine_action": point.get("prochaine_action")
                    if point
                    else None,
                    "taches_a_faire": compteurs.get(pid, 0),
                }
            )
    except ERREURS_RESEAU:
        etat["hors_ligne"] = True

    return etat


if __name__ == "__main__":
    e = recuperer_etat_rapide()
    if e["hors_ligne"]:
        print(
            "HORS LIGNE - points en attente en local :", e["en_attente"]
        )
    else:
        print(
            "envoyés :", e["envoyes"], "| restants :", e["en_attente"]
        )
    for p in e["projets"]:
        print(
            "-",
            p["nom"],
            "|",
            p["derniere_action"] or "aucun point",
            "|",
            p["prochaine_action"] or "-",
            "|",
            p["taches_a_faire"],
            "tâche(s) à faire",
        )
