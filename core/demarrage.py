from core.reprise import ERREURS_RESEAU, _lire_attente, vider_file_attente
from core.supabase_tables import SupabaseTables



def recuperer_etat_rapide():
    """Récupère l'état des projets avec trois requêtes Supabase."""
    etat = {
        "envoyes": 0, "en_attente": len(_lire_attente()),
        "projets": [], "hors_ligne": False,
    }
    try:
        etat["envoyes"], etat["en_attente"] = vider_file_attente()
        t = SupabaseTables()

        projets = t.lister("projets", statut="en_cours")
        points = t.lister_tout(
            "points_reprise", ordre="date_creation.desc,id.desc"
        )
        taches = t.lister_tout("taches", statut="a_faire")

        ids_projets = {p["id"] for p in projets}
        derniers_points = {}
        for point in points:
            pid = point.get("projet_id")
            if pid in ids_projets and pid not in derniers_points:
                derniers_points[pid] = point

        compteurs = {}
        for tache in taches:
            pid = tache.get("projet_id")
            if pid in ids_projets:
                compteurs[pid] = compteurs.get(pid, 0) + 1

        for p in projets:
            point = derniers_points.get(p["id"])
            etat["projets"].append({
                "nom": p["nom"],
                "derniere_action": point.get("derniere_action") if point else None,
                "prochaine_action": point.get("prochaine_action") if point else None,
                "taches_a_faire": compteurs.get(p["id"], 0),
            })
    except ERREURS_RESEAU:
        etat["hors_ligne"] = True
    return etat

def recuperer_etat():
    etat = {
        "envoyes": 0, "en_attente": len(_lire_attente()),
        "projets": [], "hors_ligne": False,
    }
    try:
        etat["envoyes"], etat["en_attente"] = vider_file_attente()
        t = SupabaseTables()
        for p in t.lister("projets", statut="en_cours"):
            point = t.dernier_point_reprise(p["id"])
            a_faire = t.lister("taches", projet_id=p["id"], statut="a_faire")
            etat["projets"].append({
                "nom": p["nom"],
                "derniere_action": point["derniere_action"] if point else None,
                "prochaine_action": point["prochaine_action"] if point else None,
                "taches_a_faire": len(a_faire),
            })
    except ERREURS_RESEAU:
        etat["hors_ligne"] = True
    return etat


if __name__ == "__main__":
    e = recuperer_etat()
    if e["hors_ligne"]:
        print("HORS LIGNE - points en attente en local :", e["en_attente"])
    else:
        print("envoyés :", e["envoyes"], "| restants :", e["en_attente"])
    for p in e["projets"]:
        print("-", p["nom"], "|", p["derniere_action"] or "aucun point", "|",
              p["prochaine_action"] or "-", "|", p["taches_a_faire"],
              "tâche(s) à faire")
