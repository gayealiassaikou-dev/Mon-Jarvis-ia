"""Cristallisation : memorise et rejoue les sequences d'outils qui ont reussi."""
import json
import os
import re
from datetime import datetime

from core import chemins

CHEMIN = chemins.chemin_crystallized()

# Outils autorises au rejeu (pas de suppression pour securite)
OUTILS_REJOUABLES = {
    "lire_fichier", "ecrire_fichier", "creer_dossier",
    "lister_fichiers", "executer_programme_python",
    "creer_projet", "ajouter_tache", "terminer_tache",
    "rechercher_web",
}


def _charger():
    if not os.path.exists(CHEMIN):
        return {"sequences": []}
    try:
        with open(CHEMIN, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sequences": []}


def _sauvegarder(d):
    os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
    with open(CHEMIN, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def _signature(objectif):
    """Signature normalisee, identique a learning.py."""
    s = re.sub(r"[^\w\s]", " ", str(objectif).lower())
    mots = [m for m in s.split() if len(m) > 3][:5]
    return " ".join(sorted(mots))


def enregistrer_sequence(objectif, resultats_outils):
    """Enregistre la sequence d'outils d'une sous-tache reussie.

    resultats_outils : liste des dicts de ai_engine.derniers_resultats_outils
    Chaque dict contient au moins 'outil' et 'arguments'.
    """
    if not resultats_outils:
        return None

    sequence = []
    for r in resultats_outils:
        nom = r.get("outil")
        if nom not in OUTILS_REJOUABLES:
            continue
        # Ne garder que les outils qui ont VRAIMENT reussi
        statut = r.get("statut")
        execute = r.get("execute")
        if statut != "succes" and execute is not True:
            continue
        args = r.get("arguments", {}) or {}
        if not isinstance(args, dict):
            continue
        sequence.append({"outil": nom, "arguments": args})

    if not sequence:
        return None

    sig = _signature(objectif)
    d = _charger()

    # Si une sequence identique existe deja, incrementer
    for entry in d["sequences"]:
        if entry.get("signature") == sig:
            if entry.get("sequence") == sequence:
                entry["occurrences"] = entry.get("occurrences", 1) + 1
                entry["date"] = datetime.now().isoformat(timespec="seconds")
                _sauvegarder(d)
                return entry

    nouvelle = {
        "signature": sig,
        "objectif": str(objectif)[:300],
        "sequence": sequence,
        "occurrences": 1,
        "date": datetime.now().isoformat(timespec="seconds"),
    }
    d["sequences"].append(nouvelle)
    if len(d["sequences"]) > 200:
        d["sequences"] = d["sequences"][-200:]
    _sauvegarder(d)
    return nouvelle


def trouver_sequence(objectif):
    """Cherche une sequence cristallisee pour un objectif similaire."""
    sig = _signature(objectif)
    if not sig:
        return None
    d = _charger()

    # 1. Correspondance exacte
    for entry in d["sequences"]:
        if entry.get("signature") == sig:
            return entry

    # 2. Correspondance partielle (>= 50% de mots communs)
    mots_cible = set(sig.split())
    meilleur = None
    meilleur_score = 0
    for entry in d["sequences"]:
        sig_e = entry.get("signature", "")
        if not sig_e:
            continue
        mots_e = set(sig_e.split())
        if not mots_e:
            continue
        communs = len(mots_cible & mots_e)
        seuil = max(2, len(mots_cible) // 2)
        if communs >= seuil and communs > meilleur_score:
            meilleur = entry
            meilleur_score = communs

    return meilleur


def rejouer_sequence(sequence):
    """Rejoue une sequence d'outils. Retourne {ok, resultats, erreur}."""
    if not sequence:
        return {"ok": False, "erreur": "sequence vide"}

    from core import tools

    mapping = {
        "lire_fichier": tools.lire_fichier,
        "ecrire_fichier": tools.ecrire_fichier,
        "creer_dossier": tools.creer_dossier,
        "lister_fichiers": tools.lister_fichiers,
        "executer_programme_python": tools.executer_programme_python,
        "creer_projet": tools.creer_projet,
        "ajouter_tache": tools.ajouter_tache,
        "terminer_tache": tools.terminer_tache,
        "rechercher_web": tools.rechercher_web,
    }

    resultats = []
    for etape in sequence:
        nom = etape.get("outil")
        args = etape.get("arguments", {}) or {}

        if nom not in mapping:
            return {"ok": False, "erreur": f"outil non rejouable: {nom}", "resultats": resultats}

        try:
            res = mapping[nom](**args)
            res_str = str(res).lower()
            if "erreur" in res_str[:50] or "echec" in res_str[:50]:
                return {"ok": False, "erreur": f"{nom}: {str(res)[:200]}", "resultats": resultats}
            resultats.append({"outil": nom, "resultat": str(res)[:300]})
        except Exception as e:
            return {"ok": False, "erreur": f"{nom}: {type(e).__name__}: {e}", "resultats": resultats}

    return {"ok": True, "resultats": resultats}


def etat():
    d = _charger()
    return {
        "sequences": len(d.get("sequences", [])),
        "chemin": CHEMIN,
    }
