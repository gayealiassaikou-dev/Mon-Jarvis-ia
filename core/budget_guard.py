"""Garde-fou budget : limite les tokens et appels IA par jour."""
import json
import os
from datetime import datetime

CHEMIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "budget_journalier.json")

LIMITE_APPELS_DEFAUT = int(os.getenv("JARVIS_MAX_APPELS_JOUR", "500"))
LIMITE_TOKENS_DEFAUT = int(os.getenv("JARVIS_MAX_TOKENS_JOUR", "500000"))


def _charger():
    aujourd = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(CHEMIN):
        return {"date": aujourd, "appels": 0, "tokens_estimes": 0}
    try:
        with open(CHEMIN, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") != aujourd:
            return {"date": aujourd, "appels": 0, "tokens_estimes": 0}
        return data
    except Exception:
        return {"date": aujourd, "appels": 0, "tokens_estimes": 0}


def _sauvegarder(data):
    os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
    with open(CHEMIN, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def autorise():
    data = _charger()
    if data["appels"] >= LIMITE_APPELS_DEFAUT:
        return False, f"Limite appels atteinte ({data['appels']}/{LIMITE_APPELS_DEFAUT})"
    if data["tokens_estimes"] >= LIMITE_TOKENS_DEFAUT:
        return False, f"Limite tokens atteinte ({data['tokens_estimes']}/{LIMITE_TOKENS_DEFAUT})"
    return True, "OK"


def enregistrer_appel(tokens_estimes=500):
    data = _charger()
    data["appels"] += 1
    data["tokens_estimes"] += tokens_estimes
    _sauvegarder(data)


def etat():
    data = _charger()
    return {
        "date": data["date"],
        "appels": data["appels"],
        "tokens_estimes": data["tokens_estimes"],
        "limite_appels": LIMITE_APPELS_DEFAUT,
        "limite_tokens": LIMITE_TOKENS_DEFAUT,
        "restant_appels": max(0, LIMITE_APPELS_DEFAUT - data["appels"]),
        "restant_tokens": max(0, LIMITE_TOKENS_DEFAUT - data["tokens_estimes"]),
    }
