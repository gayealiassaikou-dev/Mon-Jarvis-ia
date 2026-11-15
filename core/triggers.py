"""Declencheurs automatiques - stockage JSON."""
import json
import os
import uuid
from datetime import datetime

CHEMIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "triggers.json"
)

TYPES_VALIDES = {"timer", "fichier"}


def _charger():
    if not os.path.exists(CHEMIN):
        return {"triggers": []}
    try:
        with open(CHEMIN, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"triggers": []}


def _sauvegarder(data):
    os.makedirs(os.path.dirname(CHEMIN), exist_ok=True)
    with open(CHEMIN, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def creer_timer(nom, mission_nom, intervalle_minutes, actif=True):
    """Cree un trigger timer qui lance mission_nom toutes les N minutes."""
    if intervalle_minutes < 1:
        raise ValueError("intervalle_minutes doit etre >= 1")
    data = _charger()
    trigger = {
        "id": str(uuid.uuid4())[:8],
        "type": "timer",
        "nom": nom,
        "mission_nom": mission_nom,
        "intervalle_minutes": intervalle_minutes,
        "derniere_execution": None,
        "actif": actif,
        "date_creation": datetime.now().isoformat(timespec="seconds"),
    }
    data["triggers"].append(trigger)
    _sauvegarder(data)
    return trigger


def creer_fichier(nom, mission_nom, chemin_surveille, actif=True):
    """Cree un trigger fichier qui reagit a la modification du fichier."""
    data = _charger()
    mtime_initial = None
    if os.path.exists(chemin_surveille):
        mtime_initial = os.path.getmtime(chemin_surveille)
    trigger = {
        "id": str(uuid.uuid4())[:8],
        "type": "fichier",
        "nom": nom,
        "mission_nom": mission_nom,
        "chemin_surveille": chemin_surveille,
        "dernier_mtime": mtime_initial,
        "actif": actif,
        "date_creation": datetime.now().isoformat(timespec="seconds"),
    }
    data["triggers"].append(trigger)
    _sauvegarder(data)
    return trigger


def lister():
    return _charger()["triggers"]


def supprimer(trigger_id):
    data = _charger()
    avant = len(data["triggers"])
    data["triggers"] = [t for t in data["triggers"] if t["id"] != trigger_id]
    if len(data["triggers"]) < avant:
        _sauvegarder(data)
        return True
    return False


def basculer(trigger_id):
    data = _charger()
    for t in data["triggers"]:
        if t["id"] == trigger_id:
            t["actif"] = not t["actif"]
            _sauvegarder(data)
            return t
    return None


def marquer_execute(trigger_id):
    data = _charger()
    for t in data["triggers"]:
        if t["id"] == trigger_id:
            t["derniere_execution"] = datetime.now().isoformat(timespec="seconds")
            if t["type"] == "fichier":
                chemin = t.get("chemin_surveille")
                if chemin and os.path.exists(chemin):
                    t["dernier_mtime"] = os.path.getmtime(chemin)
            _sauvegarder(data)
            return t
    return None
