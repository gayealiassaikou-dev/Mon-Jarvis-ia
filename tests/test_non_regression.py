"""Tests non-regression sur les acquis de la session."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_contexte_brain_charge():
    """Le brain/ doit etre injecte dans le contexte."""
    from core.contexte_ia import charger_contexte
    c = charger_contexte()
    assert len(c) > 6000, f"Contexte trop court: {len(c)}"
    assert "brain/" not in c or "REGLE IMPORTANTE" in c


def test_agent_11_securise():
    """Agent 11 ne doit pas avoir tous les outils."""
    from core.agent_permissions import obtenir_outils_autorises
    outils = obtenir_outils_autorises("11_gestionnaire_outils_ia")
    assert len(outils) < 15, f"Agent 11 trop permissif: {len(outils)}"
    assert "supprimer_dossier" not in outils


def test_missions_a_reprendre_filtre():
    """Missions dangereuses exclues."""
    from core.mission_manager import MissionManager
    m = MissionManager()
    missions = m.missions_a_reprendre()
    for mission in missions:
        nom = mission.get("nom", "").lower()
        assert "supprimer le dossier core" not in nom
        assert "supprimer le fichier .env" not in nom


def test_decision_engine_fallback():
    """DecisionEngine a des providers configures."""
    from core.decision_engine import DecisionEngine
    from core.brain_manager import BrainManager
    from core.agent_manager import AgentManager
    de = DecisionEngine(BrainManager(), AgentManager(), None)
    assert len(de.providers) >= 2
    noms = [p["nom"] for p in de.providers]
    assert "groq" in noms
    assert "gemini" in noms


def test_timeouts_courts():
    """Les timeouts IA ne doivent pas depasser 30s."""
    import re
    with open("core/ai_engine.py", encoding="utf-8") as f:
        contenu = f.read()
    timeouts = re.findall(r"timeout=(\d+)", contenu)
    for t in timeouts:
        assert int(t) <= 30, f"Timeout trop long: {t}s"


def test_mission_runner_importable():
    """mission_runner et subtask_executor s'importent."""
    from core.mission_runner import executer
    from core.subtask_executor import executer_mission
    from core.mission_planner import planifier
    assert callable(executer)
    assert callable(executer_mission)
    assert callable(planifier)
