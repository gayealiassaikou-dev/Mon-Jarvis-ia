"""Test E2E reel - UNIQUEMENT avec pytest -m llm. Consomme du budget LLM."""
import os
import time
import pytest
from core.mission_manager import MissionManager
from core import budget_guard


def _tenter_mission(max_tentatives=2):
    """Lance une mission, retry si le LLM a bavarde. Max 2 tentatives."""
    from core.subtask_executor import executer_mission

    mm = MissionManager()
    for x in mm.lister_missions():
        if x["statut"] in ("en_cours", "bloquee"):
            mm.mettre_a_jour_statut(x["id"], "annulee")

    chemin = "espace_travail/reel_e2e.txt"
    resultats = []

    for tentative in range(max_tentatives):
        mission = mm.creer_mission(
            nom="Developpe un script Python qui cree espace_travail/reel_e2e.txt contenant REEL_OK",
            priorite="haute",
        )
        mm.mettre_a_jour_statut(mission["id"], "en_cours")

        try:
            t = time.time()
            r = executer_mission(mission["id"])
            duree = time.time() - t
            resultats.append({"tentative": tentative + 1, "r": r, "duree": duree})

            if r.get("ok") is True and os.path.exists(chemin):
                return {"succes": True, "tentative": tentative + 1, "r": r, "duree": duree}
        finally:
            mm.mettre_a_jour_statut(mission["id"], "annulee")

    return {"succes": False, "tentatives": resultats, "chemin": chemin}


@pytest.mark.llm
def test_pipeline_reel_mission_simple():
    """Lance une vraie mission avec LLM. Retry 2x si le LLM bavarde."""
    avant = budget_guard.etat()["restant_appels"]
    if avant < 15:
        pytest.skip(f"Budget trop bas: {avant}/500")

    resultat = _tenter_mission(max_tentatives=2)

    apres = budget_guard.etat()["restant_appels"]
    consomme = avant - apres

    print(f"\nResultat: succes={resultat['succes']}, consomme={consomme} appels")

    if not resultat["succes"]:
        # Afficher les details pour debug
        for t in resultat.get("tentatives", []):
            print(f"  Tentative {t['tentative']}: {t['r']} ({t['duree']:.1f}s)")

    assert resultat["succes"] is True, (
        f"Echec apres 2 tentatives. Resultats: {resultat.get('tentatives')}"
    )

    chemin = "espace_travail/reel_e2e.txt"
    contenu = open(chemin).read()
    print(f"Fichier OK: {repr(contenu)}")
    assert "REEL_OK" in contenu, "Contenu incorrect"

    assert consomme <= 8, f"Budget trop consomme: {consomme} (max 8)"

    # Cleanup
    try:
        os.remove(chemin)
    except Exception:
        pass
