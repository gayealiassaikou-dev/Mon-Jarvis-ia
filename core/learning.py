"""Boucle d'apprentissage : memorise les erreurs et solutions."""
import json
import os
import re
from datetime import datetime

CHEMIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "apprentissages.json"
)


def _charger():
    if not os.path.exists(CHEMIN):
        return {"echecs": [], "solutions": []}
    try:
        with open(CHEMIN, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"echecs": [], "solutions": []}


def _sauvegarder(d):
    os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
    with open(CHEMIN, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def _signature(objectif):
    """Signature normalisee pour matcher objectifs similaires."""
    s = re.sub(r"[^\w\s]", " ", str(objectif).lower())
    mots = [m for m in s.split() if len(m) > 3][:5]
    return " ".join(sorted(mots))


def enregistrer_echec(objectif, erreur, agent=None):
    """Enregistre un echec pour ameliorer les prompts futurs."""
    d = _charger()
    sig = _signature(objectif)
    # Eviter les doublons recents
    for e in d["echecs"]:
        if e.get("signature") == sig and e.get("erreur") == str(erreur)[:200]:
            e["occurrences"] = e.get("occurrences", 1) + 1
            e["date"] = datetime.now().isoformat(timespec="seconds")
            _sauvegarder(d)
            return e
    echec = {
        "signature": sig,
        "objectif": str(objectif)[:300],
        "erreur": str(erreur)[:200],
        "agent": agent,
        "occurrences": 1,
        "date": datetime.now().isoformat(timespec="seconds"),
    }
    d["echecs"].append(echec)
    # Limiter a 200 echecs
    if len(d["echecs"]) > 200:
        d["echecs"] = d["echecs"][-200:]
    _sauvegarder(d)
    return echec


def enregistrer_solution(objectif, solution, agent=None):
    """Enregistre une solution qui a marche."""
    d = _charger()
    sig = _signature(objectif)
    sol = {
        "signature": sig,
        "objectif": str(objectif)[:300],
        "solution": str(solution)[:500],
        "agent": agent,
        "date": datetime.now().isoformat(timespec="seconds"),
    }
    d["solutions"].append(sol)
    if len(d["solutions"]) > 100:
        d["solutions"] = d["solutions"][-100:]
    _sauvegarder(d)
    return sol


def conseils_pour(objectif):
    """Retourne un texte avec les erreurs passees + solutions pour un objectif similaire."""
    d = _charger()
    sig = _signature(objectif)
    if not sig:
        return ""
    lignes = []
    for e in d["echecs"]:
        if e.get("signature") == sig:
            lignes.append(f"- ECHEC passe ({e.get('occurrences', 1)}x) : {e['erreur']}")
    for s in d["solutions"]:
        if s.get("signature") == sig:
            lignes.append(f"- SOLUTION passee : {s['solution'][:200]}")
    if not lignes:
        return ""
    return "\n\nAPPRENTISSAGES PASSES (evite ces erreurs) :\n" + "\n".join(lignes[:5])


def etat():
    d = _charger()
    return {
        "echecs": len(d.get("echecs", [])),
        "solutions": len(d.get("solutions", [])),
    }
