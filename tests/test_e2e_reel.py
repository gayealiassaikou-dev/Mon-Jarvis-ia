"""Test E2E reel - UNIQUEMENT avec pytest -m llm. Consomme du budget LLM."""
import os
import time
import pytest
from core.mission_manager import MissionManager
from core import budget_guard


@pytest.mark.llm
def test_pipeline_reel_mission_simple():
    """Lance une vraie mission avec LLM. Max 5 appels budget."""
    avant = budget_guard.etat()["restant_appels"]
    if avant < 10:
        pytest.skip(f"Budget trop bas: {avant}/500")

    from core.subtask_executor import executer_mission

    mm = MissionManager()
    for x in mm.lister_missions():
        if x["statut"] in ("en_cours", "bloquee"):
            mm.mettre_a_jour_statut(x["id"], "annulee")

    mission = mm.creer_mission(
        nom="Developpe un script Python qui cree espace_travail/reel_e2e.txt contenant REEL_OK",
        priorite="haute",
    )
    mm.mettre_a_jour_statut(mission["id"], "en_cours")
    chemin = "espace_travail/reel_e2e.txt"

    try:
        t = time.time()
        r = executer_mission(mission["id"])
        duree = time.time() - t

        apres = budget_guard.etat()["restant_appels"]
        consomme = avant - apres
        print(f"\nDuree: {duree:.1f}s | Consomme: {consomme} appels")

        assert r.get("ok") is True, f"Pipeline echoue: {r}"
        assert os.path.exists(chemin), f"Fichier absent"
        assert "REEL_OK" in open(chemin).read(), "Contenu incorrect"
        assert consomme <= 6, f"Budget trop consomme: {consomme} (max 6)"
        assert duree < 30, f"Trop lent: {duree:.1f}s (max 30s)"
    finally:
        try:
            os.remove(chemin)
        except Exception:
            pass
        mm.mettre_a_jour_statut(mission["id"], "annulee")
