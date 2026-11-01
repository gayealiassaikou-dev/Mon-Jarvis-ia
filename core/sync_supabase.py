import json
import sys

from core.supabase_tables import SupabaseTables

CHEMIN = "data/projets_taches.json"


def synchroniser(ecrire=False):
    with open(CHEMIN, encoding="utf-8") as f:
        local = json.load(f)
    projets = local.get("projets", [])
    taches = local.get("taches", [])
    noms_locaux = {p["nom"] for p in projets}

    t = SupabaseTables()
    distants = {p["nom"]: p for p in t.lister("projets")}
    ids = {nom: p["id"] for nom, p in distants.items()}

    p_crees = p_presents = t_crees = t_presentes = 0
    sans_projet = []

    for p in projets:
        nom = p["nom"]
        if nom in distants:
            p_presents += 1
            print("projet déjà présent :", nom)
            continue
        p_crees += 1
        print("projet à créer :", nom, "-", p.get("statut", ""))
        if ecrire:
            nouveau = t._inserer("projets", {
                "nom": nom, "statut": {"en cours": "en_cours", "termine": "termine"}.get(p.get("statut"), "en_cours"), "objectif": "", "description": "", "prochaine_etape": "",
            })
            ids[nom] = nouveau["id"]

    deja = {}
    for i, tache in enumerate(taches):
        nom_projet = tache.get("projet")
        titre = tache["nom"]
        if nom_projet not in noms_locaux:
            sans_projet.append(titre)
            continue
        projet_id = ids.get(nom_projet)
        if projet_id and projet_id not in deja:
            deja[projet_id] = {x["titre"] for x in t.lister("taches", projet_id=projet_id)}
        if projet_id and titre in deja[projet_id]:
            t_presentes += 1
            print("tâche déjà présente :", titre)
            continue
        t_crees += 1
        print("tâche à créer :", titre, "->", nom_projet)
        if ecrire:
            t._inserer("taches", {
                "projet_id": projet_id, "titre": titre, "description": "",
                "statut": {"en attente": "a_faire", "terminee": "terminee"}.get(tache.get("statut"), "a_faire"), "ordre": i,
            })
            deja.setdefault(projet_id, set()).add(titre)

    mode = "ÉCRITURE" if ecrire else "ESSAI À BLANC (rien écrit)"
    print("---", mode)
    print("projets : à créer", p_crees, "| déjà présents", p_presents)
    print("tâches : à créer", t_crees, "| déjà présentes", t_presentes)
    print("tâches ignorées (projet inconnu) :", sans_projet)


if __name__ == "__main__":
    synchroniser(ecrire="--ecrire" in sys.argv)
