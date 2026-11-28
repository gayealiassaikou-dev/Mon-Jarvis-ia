"""Verification de l'isolation des tests (aucune donnee reelle modifiee)."""
import hashlib
import importlib
import os
from pathlib import Path

import pytest

RACINE_PROJET = Path(__file__).resolve().parent.parent

CHEMINS_ATTENDUS = (
    ("core.mission_manager", "CHEMIN_MISSIONS", ("data", "missions.json")),
    ("core.learning", "CHEMIN", ("data", "apprentissages.json")),
    ("core.crystallization", "CHEMIN", ("data", "crystallized.json")),
    ("core.budget_guard", "CHEMIN", ("data", "budget_journalier.json")),
    ("core.memory_index", "CHEMIN_MEMORY", ("memory", "memory.json")),
    ("core.memory_index", "CHEMIN_INDEX", ("memory", "memory_index.db")),
    ("core.memory_manager", "DOSSIER_MEMOIRE", ("memory",)),
    ("core.supabase_memory", "FICHIER_SESSION", ("data", ".supabase_session.json")),
    ("core.tools_projets", "CHEMIN_DONNEES", ("data", "projets_taches.json")),
    ("core.tools_projets", "CHEMIN_PROJET_ACTIF", ("data", "projet_actif.json")),
    ("core.triggers", "CHEMIN", ("data", "triggers.json")),
    ("core.paths", "DATA_DIR", ("data",)),
    ("core.paths", "MEMORY_DIR", ("memory",)),
    ("core.tools_fichiers", "DOSSIER_AUTORISE", ()),
    ("core.tools", "DOSSIER_AUTORISE", ()),
    ("core.tools_python", "DOSSIER_AUTORISE", ()),
    ("core.tools_pdf", "DOSSIER_AUTORISE", ()),
    ("core.tools_site_web", "DOSSIER_AUTORISE", ()),
    ("core.execution_python", "DOSSIER_AUTORISE", ()),
    ("core.execution_python", "DOSSIER_EXECUTION", ("espace_travail",)),
    ("core.execution_python", "FICHIER_SECRETS", (".env",)),
)


def _sha256(chemin):
    with open(chemin, "rb") as fichier:
        return hashlib.sha256(fichier.read()).hexdigest()


def _empreintes(noms):
    """Empreintes des vraies donnees du depot (jamais celles du sandbox)."""
    empreintes = {}
    for nom in noms:
        chemin = RACINE_PROJET / nom
        if chemin.exists():
            empreintes[nom] = _sha256(chemin)
    return empreintes


DONNEES_PROTEGEES = (
    "data/missions.json",
    "data/missions_archive.json",
    "data/apprentissages.json",
    "data/budget_journalier.json",
    "data/triggers.json",
    "data/projets_taches.json",
    "memory/memory_index.db",
    "memory/memory.json",
    ".supabase_session.json",
)


def test_chemins_rediriges_vers_tmp_path(tmp_path):
    """Toutes les constantes de chemins pointent dans le sandbox du test."""
    racine = str(tmp_path)
    for module_nom, attribut, morceaux in CHEMINS_ATTENDUS:
        module = importlib.import_module(module_nom)
        valeur = str(getattr(module, attribut))
        attendu = os.path.join(racine, *morceaux) if morceaux else racine
        assert valeur == attendu, f"{module_nom}.{attribut} = {valeur!r}"


def test_protections_redirigees_vers_tmp_path(tmp_path):
    """Les listes de fichiers/dossiers proteges suivent le sandbox."""
    import core.execution_python as execution_python
    import core.tools_fichiers as tools_fichiers

    racine = str(tmp_path)
    for module in (tools_fichiers, execution_python):
        assert module.FICHIERS_PROTEGES
        assert module.DOSSIERS_PROTEGES
        assert all(str(chemin).startswith(racine) for chemin in module.FICHIERS_PROTEGES)
        assert all(str(chemin).startswith(racine) for chemin in module.DOSSIERS_PROTEGES)


def test_ecriture_memoire_reste_dans_le_sandbox(tmp_path):
    """Une ecriture via MemoryManager reste dans tmp_path, donnees intactes."""
    from core.memory_manager import MemoryManager

    avant = _empreintes(DONNEES_PROTEGEES)
    gestionnaire = MemoryManager()
    gestionnaire.ajouter_souvenir({"texte": "isolation"})

    assert str(gestionnaire.chemin).startswith(str(tmp_path))
    assert os.path.exists(tmp_path / "memory" / "memory.json")
    assert _empreintes(DONNEES_PROTEGEES) == avant


def test_ecriture_missions_reste_dans_le_sandbox(tmp_path):
    """Une creation de mission reste dans tmp_path, donnees intactes."""
    from core.mission_manager import MissionManager

    avant = _empreintes(DONNEES_PROTEGEES)
    gestionnaire = MissionManager()
    mission = gestionnaire.creer_mission("Mission isolee", "Objectif")

    assert mission["id"]
    assert os.path.exists(tmp_path / "data" / "missions.json")
    assert _empreintes(DONNEES_PROTEGEES) == avant


def test_archives_redirigees(tmp_path):
    """Les archives missions et mémoire restent dans le sandbox."""
    from core.memory_manager import MemoryManager
    from core.mission_manager import MissionManager

    gestionnaire = MissionManager()
    mission = gestionnaire.creer_mission("Mission archivee", "Objectif")
    gestionnaire.mettre_a_jour_statut(mission["id"], "annulee")
    gestionnaire.purger(jours=0)
    assert os.path.exists(tmp_path / "data" / "missions_archive.json")

    memoire = MemoryManager()
    memoire.limite_historique = 0
    memoire.ajouter_echange("question", "reponse")
    assert os.path.exists(tmp_path / "memory" / "historique_archive.json")


def test_espace_travail_isole_retourne_le_sandbox(tmp_path, espace_travail_isole):
    """La fixture E2E designe le meme sandbox que l'isolation automatique."""
    assert str(espace_travail_isole) == str(tmp_path)
    assert os.path.isdir(tmp_path / "espace_travail")


def test_sandbox_import_hors_du_depot():
    """Les effets de bord a l'import (Jarvis/MemoryManager) sont sandboxed."""
    import conftest as configuration

    sandbox = str(configuration.SANDBOX_IMPORT)
    assert os.path.isdir(sandbox)
    assert not sandbox.startswith(str(configuration.RACINE_PROJET) + os.sep)
    assert sandbox != str(configuration.RACINE_PROJET)


def test_patch_non_applique_est_signale():
    """Un attribut de chemin absent n'est plus ignore en silence."""
    import conftest as configuration

    manquants = []
    configuration._appliquer(
        ("core.mission_manager", "ATTRIBUT_INEXISTANT", "valeur"),
        [],
        manquants,
    )
    assert manquants, "un attribut absent doit etre signale"
    assert "ATTRIBUT_INEXISTANT" in manquants[0]
