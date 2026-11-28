"""Resolution centralisee des chemins de donnees de Jarvis.

Les modules lisent ces chemins a l'import. Pour les tests, les variables
d'environnement ``JARVIS_DATA_DIR`` et ``JARVIS_MEMORY_DIR`` permettent de
rediriger les donnees vers des repertoires temporaires. Sans ces variables,
le comportement historique de l'application est conserve.
"""
import os
from pathlib import Path

RACINE_PROJET = Path(__file__).resolve().parent.parent


def _dossier(variable, defaut):
    """Retourne le dossier surcharge par l'environnement, sinon le defaut."""
    valeur = os.getenv(variable)
    if valeur:
        return os.path.abspath(os.path.expanduser(valeur))
    return str(defaut)


def dossier_donnees():
    """Dossier des donnees applicatives (data/ par defaut)."""
    return _dossier("JARVIS_DATA_DIR", RACINE_PROJET / "data")


def dossier_memoire():
    """Dossier de la memoire persistante (memory/ par defaut)."""
    return _dossier("JARVIS_MEMORY_DIR", RACINE_PROJET / "memory")


def chemin_donnees(nom):
    return os.path.join(dossier_donnees(), nom)


def chemin_memoire(nom):
    return os.path.join(dossier_memoire(), nom)


def chemin_missions():
    return chemin_donnees("missions.json")


def chemin_missions_archive():
    return chemin_donnees("missions_archive.json")


def chemin_apprentissages():
    return chemin_donnees("apprentissages.json")


def chemin_crystallized():
    return chemin_donnees("crystallized.json")


def chemin_triggers():
    return chemin_donnees("triggers.json")


def chemin_projets_taches():
    return chemin_donnees("projets_taches.json")


def chemin_projet_actif():
    return chemin_donnees("projet_actif.json")


def chemin_budget():
    return chemin_donnees("budget_journalier.json")


def chemin_memory_json():
    return chemin_memoire("memory.json")


def chemin_memory_index():
    return chemin_memoire("memory_index.db")


def fichier_session_supabase():
    """Fichier de session Supabase.

    Par defaut il reste a la racine du projet (comportement historique).
    Il n'est redirige que si ``JARVIS_DATA_DIR`` est defini.
    """
    valeur = os.getenv("JARVIS_DATA_DIR")
    if valeur:
        dossier = os.path.abspath(os.path.expanduser(valeur))
        return os.path.join(dossier, ".supabase_session.json")
    return str(RACINE_PROJET / ".supabase_session.json")


def dossier_espace_travail():
    """Espace de travail des executions (espace_travail/ par defaut)."""
    return _dossier("JARVIS_WORK_DIR", RACINE_PROJET / "espace_travail")
