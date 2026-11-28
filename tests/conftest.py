"""Configuration pytest : isolation complete des donnees et du travail.

Chaque test s'execute dans ``tmp_path`` :

* les donnees persistantes (missions, archive, apprentissages, cristallisation,
  budget, memoire, index, projets, triggers, session Supabase) sont redirigees
  vers ``tmp_path/data`` et ``tmp_path/memory`` ;
* la racine des outils fichiers et l'espace de travail sont rediriges vers
  ``tmp_path`` et ``tmp_path/espace_travail``, et le repertoire courant y est
  place pour que les chemins relatifs ``espace_travail/...`` designent le
  sandbox ;
* pour les tests ``@llm`` le budget n'est **pas** neutralise : une copie du
  fichier budget reel est placee dans le sandbox, les quotas reels restent donc
  actifs et aucune ecriture n'atteint ``data/budget_journalier.json``.

Aucun patch n'est applique en silence : un module ou un attribut indispensable
manquant fait echouer le test au demarrage. Le module ``tests/test_isolation_llm.py``
desactive l'isolation automatique (``ISOLATION_MANUELLE``) pour tester lui-meme
le chemin ``@llm`` sans appel reseau.
"""
import atexit
import contextlib
import importlib
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

RACINE_PROJET = Path(__file__).resolve().parent.parent

# Sandbox d'import : certains modules creent des objets des l'import (par
# exemple ``interface/app.py`` instancie ``Jarvis()`` donc ``MemoryManager()``).
# Les variables sont posees avant l'import des modules de test pour que ces
# effets de bord n'ecrivent jamais dans les vrais ``data/`` et ``memory/``.
SANDBOX_IMPORT = Path(tempfile.mkdtemp(prefix="jarvis_pytest_import_"))
for _sous_dossier in ("data", "memory", "espace_travail"):
    (SANDBOX_IMPORT / _sous_dossier).mkdir(parents=True, exist_ok=True)
os.environ["JARVIS_DATA_DIR"] = str(SANDBOX_IMPORT / "data")
os.environ["JARVIS_MEMORY_DIR"] = str(SANDBOX_IMPORT / "memory")
os.environ["JARVIS_WORK_DIR"] = str(SANDBOX_IMPORT / "espace_travail")
atexit.register(shutil.rmtree, SANDBOX_IMPORT, True)

FONCTIONS_BUDGET_NEUTRALISEES = (
    "autorise",
    "autorise_mission",
    "enregistrer_appel",
    "enregistrer_appel_mission",
    "reinitialiser_mission",
    "_sauvegarder",
)


def _cibles_donnees(dossier_data, dossier_memoire):
    """Constantes de chemins de donnees a rediriger, module par module."""
    return (
        ("core.mission_manager", "CHEMIN_MISSIONS",
         str(dossier_data / "missions.json")),
        ("core.learning", "CHEMIN",
         str(dossier_data / "apprentissages.json")),
        ("core.crystallization", "CHEMIN",
         str(dossier_data / "crystallized.json")),
        ("core.budget_guard", "CHEMIN",
         str(dossier_data / "budget_journalier.json")),
        ("core.memory_index", "CHEMIN_MEMORY",
         str(dossier_memoire / "memory.json")),
        ("core.memory_index", "CHEMIN_INDEX",
         str(dossier_memoire / "memory_index.db")),
        ("core.memory_manager", "DOSSIER_MEMOIRE", str(dossier_memoire)),
        ("core.supabase_memory", "FICHIER_SESSION",
         dossier_data / ".supabase_session.json"),
        ("core.paths", "DATA_DIR", dossier_data),
        ("core.paths", "MEMORY_DIR", dossier_memoire),
        ("core.tools_projets", "CHEMIN_DONNEES",
         str(dossier_data / "projets_taches.json")),
        ("core.tools_projets", "CHEMIN_PROJET_ACTIF",
         str(dossier_data / "projet_actif.json")),
        ("core.tools", "CHEMIN_DONNEES",
         str(dossier_data / "projets_taches.json")),
        ("core.tools", "CHEMIN_PROJET_ACTIF",
         str(dossier_data / "projet_actif.json")),
        ("core.triggers", "CHEMIN", str(dossier_data / "triggers.json")),
    )


def _cibles_travail(racine):
    """Racines d'outils et de travail a confiner dans ``racine``."""
    espace_travail = racine / "espace_travail"
    fichiers_proteges = [
        str(racine / ".env"),
        str(racine / ".supabase_session.json"),
        str(racine / ".git"),
    ]
    dossiers_proteges = [
        str(racine / "core"),
        str(racine / ".git"),
        str(racine / "memory"),
        str(racine / "data"),
        str(racine / "backups"),
        str(racine / ".patches"),
        str(racine / "interface" / "data"),
    ]
    return (
        ("core.tools_fichiers", "DOSSIER_AUTORISE", str(racine)),
        ("core.tools_fichiers", "FICHIERS_PROTEGES", fichiers_proteges),
        ("core.tools_fichiers", "DOSSIERS_PROTEGES", dossiers_proteges),
        ("core.tools", "DOSSIER_AUTORISE", str(racine)),
        ("core.tools_python", "DOSSIER_AUTORISE", str(racine)),
        ("core.tools_projets", "DOSSIER_AUTORISE", str(racine)),
        ("core.tools_pdf", "DOSSIER_AUTORISE", str(racine)),
        ("core.tools_site_web", "DOSSIER_AUTORISE", str(racine)),
        ("core.execution_python", "DOSSIER_AUTORISE", str(racine)),
        ("core.execution_python", "DOSSIER_EXECUTION", str(espace_travail)),
        ("core.execution_python", "FICHIER_SECRETS", str(racine / ".env")),
        ("core.execution_python", "FICHIERS_PROTEGES", list(fichiers_proteges)),
        ("core.execution_python", "DOSSIERS_PROTEGES", list(dossiers_proteges)),
    )


def _appliquer(cible, patchers, manquants):
    """Applique un patch de constante et verifie qu'il est effectif."""
    module_nom, attribut, valeur = cible
    try:
        module = importlib.import_module(module_nom)
    except ImportError as erreur:
        manquants.append(f"{module_nom} : import impossible ({erreur})")
        return
    if not hasattr(module, attribut):
        manquants.append(f"{module_nom}.{attribut} : attribut absent")
        return
    patcher = mock.patch.object(module, attribut, valeur)
    patcher.start()
    if getattr(module, attribut) is not valeur:
        patcher.stop()
        manquants.append(f"{module_nom}.{attribut} : patch non applique")
        return
    patchers.append(patcher)


@contextlib.contextmanager
def _isolation(tmp_path, monkeypatch, llm):
    """Isole donnees et espace de travail ; budget reel si ``llm``."""
    racine = Path(tmp_path)
    dossier_data = racine / "data"
    dossier_memoire = racine / "memory"
    dossier_travail = racine / "espace_travail"
    for dossier in (dossier_data, dossier_memoire, dossier_travail):
        dossier.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("JARVIS_DATA_DIR", str(dossier_data))
    monkeypatch.setenv("JARVIS_MEMORY_DIR", str(dossier_memoire))
    monkeypatch.setenv("JARVIS_WORK_DIR", str(dossier_travail))

    manquants = []
    patchers = []
    for cible in _cibles_donnees(dossier_data, dossier_memoire) + _cibles_travail(racine):
        _appliquer(cible, patchers, manquants)

    budget = importlib.import_module("core.budget_guard")
    if not llm:
        for attribut in ("_session", "_missions") + FONCTIONS_BUDGET_NEUTRALISEES:
            if not hasattr(budget, attribut):
                manquants.append(f"core.budget_guard.{attribut} : attribut absent")

    if manquants:
        for patcher in reversed(patchers):
            patcher.stop()
        pytest.fail(
            "Isolation des tests incomplete :\n- " + "\n- ".join(manquants)
        )

    if llm:
        # Quota reel conserve : copie scellee du budget, ecritures dans le sandbox.
        source = RACINE_PROJET / "data" / "budget_journalier.json"
        if source.exists():
            shutil.copyfile(source, dossier_data / "budget_journalier.json")
    else:
        budget._session.update({"appels": 0, "tokens": 0})
        budget._missions.clear()

    monkeypatch.chdir(racine)
    try:
        if llm:
            yield racine
            return
        with contextlib.ExitStack() as pile:
            pile.enter_context(
                mock.patch("core.budget_guard.autorise", return_value=(True, "OK"))
            )
            pile.enter_context(
                mock.patch(
                    "core.budget_guard.autorise_mission", return_value=(True, "OK")
                )
            )
            pile.enter_context(
                mock.patch("core.budget_guard.enregistrer_appel", return_value=None)
            )
            pile.enter_context(
                mock.patch(
                    "core.budget_guard.enregistrer_appel_mission", return_value=None
                )
            )
            pile.enter_context(
                mock.patch("core.budget_guard.reinitialiser_mission", return_value=None)
            )
            pile.enter_context(
                mock.patch("core.budget_guard._sauvegarder", return_value=None)
            )
            yield racine
    finally:
        for patcher in reversed(patchers):
            patcher.stop()


@pytest.fixture(autouse=True)
def _isolation_automatique(request, tmp_path, monkeypatch):
    """Isole chaque test ; laisse la main si le module le demande."""
    if getattr(request.module, "ISOLATION_MANUELLE", False):
        yield tmp_path
        return
    marqueur_llm = request.node.get_closest_marker("llm") is not None
    with _isolation(tmp_path, monkeypatch, llm=marqueur_llm) as racine:
        yield racine


@pytest.fixture
def espace_travail_isole(tmp_path):
    """Retourne le sandbox de travail du test (isolation deja appliquee)."""
    return tmp_path
