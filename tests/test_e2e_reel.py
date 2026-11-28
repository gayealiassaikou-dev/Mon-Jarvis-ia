"""Test E2E reel - UNIQUEMENT avec pytest -m llm. Consomme du budget LLM.

Toutes les ecritures restent dans le sandbox pytest (``tmp_path``) : les
missions, la memoire, le budget et l'espace de travail reels ne sont jamais
modifies. Aucun nettoyage ne sort du sandbox et aucun fichier de
``.github/workflows/`` n'est touche.
"""
import glob
import os
import time

import pytest

from core import budget_guard
from core.mission_manager import MissionManager

MOTIFS_RESIDUS = (
    "create_*.py",
    "reel_*.py",
    "_e2e_*.py",
    "sous_tache_*.py",
    "reel_e2e.txt",
)


def _dossier_travail():
    return os.path.join(os.getcwd(), "espace_travail")


def _verifier_sandbox(chemin):
    """Refuse tout chemin hors du repertoire courant (sandbox pytest)."""
    racine = os.path.realpath(os.getcwd())
    reel = os.path.realpath(chemin)
    if reel != racine and not reel.startswith(racine + os.sep):
        raise AssertionError(f"chemin hors du sandbox de test : {reel}")
    return reel


def _nettoyer_residus():
    """Supprime uniquement les fichiers produits dans le sandbox du test."""
    dossier = _verifier_sandbox(_dossier_travail())
    for motif in MOTIFS_RESIDUS:
        for chemin in glob.glob(os.path.join(dossier, motif)):
            _verifier_sandbox(chemin)
            try:
                os.remove(chemin)
            except OSError:
                pass


def _tenter_mission(max_tentatives=2):
    """Lance une mission, retry si le LLM a bavarde. Max 2 tentatives."""
    from core.subtask_executor import executer_mission

    _nettoyer_residus()

    mm = MissionManager()
    for x in mm.lister_missions():
        if x["statut"] in ("en_cours", "bloquee"):
            mm.mettre_a_jour_statut(x["id"], "annulee")

    chemin = os.path.join("espace_travail", "reel_e2e.txt")
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
        for t in resultat.get("tentatives", []):
            print(f"  Tentative {t['tentative']}: {t['r']} ({t['duree']:.1f}s)")

    assert resultat["succes"] is True, (
        f"Echec apres 2 tentatives. Resultats: {resultat.get('tentatives')}"
    )

    chemin = os.path.join("espace_travail", "reel_e2e.txt")
    with open(chemin, encoding="utf-8") as fichier:
        contenu = fichier.read()
    print(f"Fichier OK: {repr(contenu)}")
    assert "REEL_OK" in contenu, "Contenu incorrect"

    assert consomme <= 8, f"Budget trop consomme: {consomme} (max 8)"

    _nettoyer_residus()
    try:
        os.remove(chemin)
    except OSError:
        pass
