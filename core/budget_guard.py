"""Garde-fou budget : limite les tokens et appels IA par jour."""
import json
import os
from datetime import datetime

CHEMIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "budget_journalier.json")

LIMITE_APPELS_DEFAUT = int(os.getenv("JARVIS_MAX_APPELS_JOUR", "500"))
LIMITE_TOKENS_DEFAUT = int(os.getenv("JARVIS_MAX_TOKENS_JOUR", "500000"))
LIMITE_SESSION_DEFAUT = int(os.getenv("JARVIS_MAX_APPELS_SESSION", "100"))

# Compteur de session (reset a chaque nouveau process Python)
_session = {"appels": 0, "tokens": 0}

# Compteur par mission (reset manuel entre missions)
_missions = {}

LIMITE_MISSION_DEFAUT = int(os.getenv("JARVIS_MAX_APPELS_MISSION", "15"))


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
    restant = LIMITE_APPELS_DEFAUT - data["appels"]
    # Verifier limite session d'abord
    if _session["appels"] >= LIMITE_SESSION_DEFAUT:
        return False, f"Limite session atteinte ({_session['appels']}/{LIMITE_SESSION_DEFAUT})"
    if data["appels"] >= LIMITE_APPELS_DEFAUT:
        try:
            from core import notifications
            notifications.budget_alerte(0, LIMITE_APPELS_DEFAUT)
        except Exception:
            pass
        return False, f"Limite appels atteinte ({data['appels']}/{LIMITE_APPELS_DEFAUT})"
    if data["tokens_estimes"] >= LIMITE_TOKENS_DEFAUT:
        return False, f"Limite tokens atteinte ({data['tokens_estimes']}/{LIMITE_TOKENS_DEFAUT})"
    # Alerte a 50 appels restants
    if restant == 50:
        try:
            from core import notifications
            notifications.budget_alerte(restant, LIMITE_APPELS_DEFAUT)
        except Exception:
            pass
    return True, "OK"


def autorise_mission(mission_id):
    """Verifie si une mission a encore du budget."""
    if not mission_id:
        return True, "OK"
    compte = _missions.get(mission_id, 0)
    if compte >= LIMITE_MISSION_DEFAUT:
        return False, f"Limite mission atteinte ({compte}/{LIMITE_MISSION_DEFAUT})"
    return True, "OK"


def enregistrer_appel_mission(mission_id):
    """Incremente le compteur de la mission."""
    if not mission_id:
        return
    _missions[mission_id] = _missions.get(mission_id, 0) + 1


def reinitialiser_mission(mission_id):
    """Remet a zero le compteur d'une mission."""
    if mission_id in _missions:
        del _missions[mission_id]


def enregistrer_appel(tokens_estimes=500):
    data = _charger()
    data["appels"] += 1
    data["tokens_estimes"] += tokens_estimes
    _sauvegarder(data)
    _session["appels"] += 1
    _session["tokens"] += tokens_estimes


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
        # Session (process actuel)
        "session_appels": _session["appels"],
        "session_tokens": _session["tokens"],
        "session_limite": LIMITE_SESSION_DEFAUT,
        "session_restant": max(0, LIMITE_SESSION_DEFAUT - _session["appels"]),
    }
