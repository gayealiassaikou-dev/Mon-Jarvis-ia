"""Notifications Android via termux-api."""
import subprocess
import shutil


def _dispo():
    return shutil.which("termux-notification") is not None


def envoyer(titre, contenu, priorite="default"):
    if not _dispo():
        return False
    try:
        subprocess.run(
            ["termux-notification",
             "--title", str(titre)[:80],
             "--content", str(contenu)[:300],
             "--priority", priorite],
            timeout=5,
            capture_output=True,
            check=False,
        )
        return True
    except Exception:
        return False


def mission_terminee(mission_id, nom, duree_s=None):
    contenu = f"Mission {mission_id} : {nom[:100]}"
    if duree_s:
        contenu += f" ({duree_s:.1f}s)"
    return envoyer("Jarvis — Mission terminee", contenu)


def mission_echouee(mission_id, nom, raison=""):
    contenu = f"Mission {mission_id} : {nom[:100]}"
    if raison:
        contenu += f" | {raison[:150]}"
    return envoyer("Jarvis — Mission echouee", contenu, priorite="high")


def budget_alerte(restant, limite):
    return envoyer("Jarvis — Budget bas", f"{restant}/{limite} appels restants", priorite="high")
