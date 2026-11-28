"""Test E2E offline du pipeline complet (0 LLM, tout mocke).

Toutes les ecritures passent par la fixture ``espace_travail_isole`` :
missions, apprentissages, cristallisation, budget et fichiers de travail
sont confines dans le repertoire temporaire du test. Aucune donnee reelle
de Jarvis n'est lue ni modifiee.
"""
import os
import sys
import json
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline_deterministe(espace_travail_isole):
    """Mission simple -> deterministe -> fichier cree -> mission terminee. 0 LLM."""
    from core.mission_manager import MissionManager
    from core.subtask_executor import executer_mission

    chemin = "espace_travail/e2e_det.txt"
    mm = MissionManager()
    mission = mm.creer_mission(
        nom="Ecris le fichier espace_travail/e2e_det.txt contenant DET_OK",
        priorite="haute",
    )
    mm.mettre_a_jour_statut(mission["id"], "en_cours")
    mm.ajouter_sous_tache(
        mission["id"], "01_developpeur",
        "Ecris le fichier espace_travail/e2e_det.txt contenant DET_OK",
        [],
    )

    r = executer_mission(mission["id"], auto_planifier=False)
    assert r.get("ok") is True, f"Echec pipeline: {r}"
    assert os.path.exists(chemin), f"Fichier absent: {chemin}"
    with open(chemin, encoding="utf-8") as fichier:
        assert "DET_OK" in fichier.read()
    # Le fichier est bien dans le bac a sable, pas dans le vrai espace_travail.
    assert os.path.realpath(chemin).startswith(str(espace_travail_isole))


def test_pipeline_fallback_json(espace_travail_isole):
    """Mission avec LLM qui renvoie JSON -> fallback JSON -> fichier cree. 0 LLM reel."""
    from core.mission_manager import MissionManager
    import core.jarvis

    class FakeJarvis:
        def __init__(self):
            self.ai_engine = type("obj", (object,), {"derniers_resultats_outils": []})()
        def traiter_commande(self, *a, **k):
            return json.dumps({
                "action": "ecrire_fichier",
                "parameters": {
                    "chemin": "espace_travail/e2e_json.txt",
                    "contenu": "JSON_OK",
                },
            })

    orig = core.jarvis.Jarvis
    core.jarvis.Jarvis = FakeJarvis
    chemin = "espace_travail/e2e_json.txt"
    try:
        from core.subtask_executor import executer_mission

        mm = MissionManager()
        mission = mm.creer_mission(nom="Cree un fichier via JSON", priorite="haute")
        mm.mettre_a_jour_statut(mission["id"], "en_cours")
        mm.ajouter_sous_tache(
            mission["id"], "01_developpeur",
            "Cree un fichier espace_travail/e2e_json.txt contenant JSON_OK",
            [],
        )

        r = executer_mission(mission["id"], auto_planifier=False)
        assert r.get("ok") is True, f"Pipeline echoue: {r}"
        assert os.path.exists(chemin), f"Fichier absent: {chemin}"
        with open(chemin, encoding="utf-8") as fichier:
            assert "JSON_OK" in fichier.read()
        assert os.path.realpath(chemin).startswith(str(espace_travail_isole))
    finally:
        core.jarvis.Jarvis = orig


def test_pipeline_fallback_python(espace_travail_isole):
    """Mission avec LLM qui renvoie ```python -> fallback python -> fichier cree."""
    from core.mission_manager import MissionManager
    import core.jarvis

    class FakeJarvis:
        def __init__(self):
            self.ai_engine = type("obj", (object,), {"derniers_resultats_outils": []})()
        def traiter_commande(self, *a, **k):
            return '```python\nfrom pathlib import Path\np = Path("espace_travail")\np.mkdir(exist_ok=True)\n(p / "e2e_py.txt").write_text("PY_OK")\nprint("OK")\n```'

    orig = core.jarvis.Jarvis
    core.jarvis.Jarvis = FakeJarvis
    chemin = "espace_travail/e2e_py.txt"
    try:
        from core.subtask_executor import executer_mission

        mm = MissionManager()
        mission = mm.creer_mission(nom="Cree fichier via python", priorite="haute")
        mm.mettre_a_jour_statut(mission["id"], "en_cours")
        mm.ajouter_sous_tache(
            mission["id"], "01_developpeur",
            "Developpe un script qui cree espace_travail/e2e_py.txt",
            [],
        )

        r = executer_mission(mission["id"], auto_planifier=False)
        assert r.get("ok") is True, f"Pipeline echoue: {r}"
        dossier = os.listdir("espace_travail") if os.path.exists("espace_travail") else "N/A"
        assert os.path.exists(chemin), f"Fichier absent. Dossier: {dossier}"
        assert not os.path.exists("espace_travail/espace_travail"), "Bug double dossier"
        assert os.path.realpath(chemin).startswith(str(espace_travail_isole))
    finally:
        core.jarvis.Jarvis = orig


def test_pipeline_dependances(espace_travail_isole):
    """2 sous-taches dependantes -> executees dans l'ordre. 0 LLM."""
    from core.mission_manager import MissionManager
    from core.subtask_executor import executer_mission

    mm = MissionManager()
    mission = mm.creer_mission(nom="Test dependances", priorite="haute")
    mm.mettre_a_jour_statut(mission["id"], "en_cours")
    st1 = mm.ajouter_sous_tache(
        mission["id"], "01_developpeur",
        "Ecris le fichier espace_travail/step1.txt contenant STEP1",
        [],
    )
    mm.ajouter_sous_tache(
        mission["id"], "01_developpeur",
        "Ecris le fichier espace_travail/step2.txt contenant STEP2",
        [st1["id"]],
    )

    r = executer_mission(mission["id"], auto_planifier=False)
    assert r.get("ok") is True, f"Pipeline echoue: {r}"
    assert r.get("etapes") == 2
    assert os.path.exists("espace_travail/step1.txt")
    assert os.path.exists("espace_travail/step2.txt")
    assert os.path.realpath("espace_travail/step1.txt").startswith(
        str(espace_travail_isole)
    )


def test_pipeline_faux_succes_detecte(espace_travail_isole):
    """LLM bavard qui demande confirmation -> ECHEC detecte."""
    from core.mission_manager import MissionManager
    import core.jarvis

    class FakeJarvisBavard:
        def __init__(self):
            self.ai_engine = type("obj", (object,), {"derniers_resultats_outils": []})()
        def traiter_commande(self, *a, **k):
            return "Voulez-vous que je cree ce fichier ? Confirmez avant d'agir."

    orig = core.jarvis.Jarvis
    core.jarvis.Jarvis = FakeJarvisBavard
    try:
        from core.subtask_executor import executer_mission

        mm = MissionManager()
        mission = mm.creer_mission(nom="Test bavard", priorite="haute")
        mm.mettre_a_jour_statut(mission["id"], "en_cours")
        # "Developpe un script" pour contourner le deterministe
        mm.ajouter_sous_tache(
            mission["id"], "01_developpeur",
            "Developpe un script Python qui cree espace_travail/faux.txt",
            [],
        )

        r = executer_mission(mission["id"], auto_planifier=False)
        assert r.get("ok") is False, f"Faux succes non detecte: {r}"
        assert r.get("statut") in ("bloquee", "exception")
        assert not os.path.exists("espace_travail/faux.txt")
    finally:
        core.jarvis.Jarvis = orig
