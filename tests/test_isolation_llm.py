"""Verification du chemin @llm sans aucun appel reseau ni LLM reel.

L'isolation automatique est desactivee dans ce module pour pouvoir tester
directement le contexte ``_isolation(..., llm=True)`` de ``conftest.py``.
"""

import pytest

import conftest as configuration

ISOLATION_MANUELLE = True


def test_llm_garde_le_quota_reel_et_ecrit_dans_le_sandbox(tmp_path, monkeypatch):
    import core.budget_guard as budget
    import core.mission_manager as mission_manager

    autorise_reel = budget.autorise
    enregistrer_reel = budget.enregistrer_appel
    reel = configuration.RACINE_PROJET / "data" / "budget_journalier.json"

    with configuration._isolation(tmp_path, monkeypatch, llm=True):
        assert str(budget.CHEMIN).startswith(str(tmp_path))
        copie = tmp_path / "data" / "budget_journalier.json"
        if reel.exists():
            assert copie.read_bytes() == reel.read_bytes()
        else:
            pytest.skip("fichier budget reel absent")

        # Le controle de quota n'est pas neutralise.
        assert budget.autorise is autorise_reel
        assert budget.enregistrer_appel is enregistrer_reel

        # La consommation est calculee depuis la copie initiale.
        avant = budget.etat()["appels"]
        budget.enregistrer_appel()
        assert budget.etat()["appels"] == avant + 1

        # Les donnees de mission sont isolees elles aussi.
        assert str(mission_manager.CHEMIN_MISSIONS).startswith(str(tmp_path))


def test_llm_ne_modifie_pas_le_budget_reel(tmp_path, monkeypatch):
    import hashlib

    reel = configuration.RACINE_PROJET / "data" / "budget_journalier.json"
    if not reel.exists():
        pytest.skip("fichier budget reel absent")
    avant = hashlib.sha256(reel.read_bytes()).hexdigest()

    with configuration._isolation(tmp_path, monkeypatch, llm=True):
        import core.budget_guard as budget
        budget.enregistrer_appel()
        budget.enregistrer_appel()

    apres = hashlib.sha256(reel.read_bytes()).hexdigest()
    assert apres == avant, "le budget reel ne doit jamais etre modifie"


def test_llm_donnees_missions_isolees(tmp_path, monkeypatch):
    from core.mission_manager import MissionManager

    with configuration._isolation(tmp_path, monkeypatch, llm=True):
        gestionnaire = MissionManager()
        gestionnaire.creer_mission("Mission llm simulee", "Objectif")
        assert (tmp_path / "data" / "missions.json").exists()
