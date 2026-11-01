import json
import os
import sys
import time

import requests

from core.supabase_memory import SupabaseMemoryError
from core.supabase_tables import SupabaseTables

FILE_ATTENTE = "data/reprise_en_attente.jsonl"
ERREURS_RESEAU = (SupabaseMemoryError, requests.RequestException)


def _projet_id(t, nom):
    lignes = t.lister("projets", nom=nom)
    if not lignes:
        raise ValueError("Projet inconnu dans Supabase : " + nom)
    return lignes[0]["id"]


def _lire_attente():
    if not os.path.exists(FILE_ATTENTE):
        return []
    with open(FILE_ATTENTE, encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f if ligne.strip()]


def _ecrire_attente(entrees):
    os.makedirs("data", exist_ok=True)
    with open(FILE_ATTENTE, "w", encoding="utf-8") as f:
        for e in entrees:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _envoyer(t, e):
    pid = _projet_id(t, e["projet"])
    if e.get("type_evenement"):
        t.ajouter_historique(
            pid, e["type_evenement"], e.get("description", ""),
            e.get("resultat", ""), e.get("donnees"),
        )
        return
    t.ajouter_point_reprise(
        pid, e["derniere_action"], e.get("derniere_etape", ""),
        e.get("prochaine_action", ""), e.get("fichiers"),
        e.get("contexte", ""), e.get("blocages", ""),
    )
    t.ajouter_historique(
        pid, "point_reprise", e["derniere_action"], "",
        {"prochaine_action": e.get("prochaine_action", "")},
    )


def sauvegarder_point(projet, derniere_action, derniere_etape="",
                      prochaine_action="", fichiers=None, contexte="",
                      blocages=""):
    entree = {
        "projet": projet, "derniere_action": derniere_action,
        "derniere_etape": derniere_etape, "prochaine_action": prochaine_action,
        "fichiers": fichiers or [], "contexte": contexte, "blocages": blocages,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        _envoyer(SupabaseTables(), entree)
        return "supabase"
    except ERREURS_RESEAU:
        _ecrire_attente(_lire_attente() + [entree])
        return "local"


def noter_evenement(projet, type_evenement, description="", resultat="",
                    donnees=None):
    entree = {
        "projet": projet, "type_evenement": type_evenement,
        "description": description, "resultat": resultat,
        "donnees": donnees or {}, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        _envoyer(SupabaseTables(), entree)
        return "supabase"
    except ERREURS_RESEAU:
        _ecrire_attente(_lire_attente() + [entree])
        return "local"


def vider_file_attente():
    en_attente = _lire_attente()
    restantes = []
    envoyes = 0
    t = SupabaseTables()
    for i, e in enumerate(en_attente):
        try:
            _envoyer(t, e)
            envoyes += 1
        except (ERREURS_RESEAU, ValueError):
            restantes = en_attente[i:]
            break
    _ecrire_attente(restantes)
    return envoyes, len(restantes)


def reprendre(projet):
    locaux = [e for e in _lire_attente() if e["projet"] == projet and not e.get("type_evenement")]
    if locaux:
        return "local", locaux[-1]
    try:
        t = SupabaseTables()
        point = t.dernier_point_reprise(_projet_id(t, projet))
        if point:
            return "supabase", point
    except ERREURS_RESEAU:
        pass
    return None, None


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["sauver"] and len(a) >= 4:
        print(sauvegarder_point(a[1], a[2], prochaine_action=a[3]))
    elif a[:1] == ["reprendre"] and len(a) >= 2:
        source, p = reprendre(a[1])
        if p:
            print(source, "|", p["derniere_action"], "|", p["prochaine_action"])
        else:
            print("aucun point de reprise")
    elif a[:1] == ["noter"] and len(a) >= 4:
        print(noter_evenement(a[1], a[2], a[3]))
    elif a[:1] == ["vider"]:
        print(vider_file_attente())
    else:
        print('Usage : sauver "Projet" "action" "prochaine" | reprendre "Projet" | vider')
