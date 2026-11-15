"""Tests offline : detection des faux succes (0 appel LLM)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _simuler_detection(reponse, objectif):
    """Reproduit la logique de detection de subtask_executor sans LLM."""
    SIGNES_ECHEC = [
        "validation echouee", "je n'ai pas pu confirmer",
        "erreur ia", "aucun outil execute",
        "reussite non prouvee", "action(s) en echec",
        "je ne peux pas", "je ne suis pas en mesure",
        "que souhaitez-vous", "voulez-vous que je",
        "a votre confirmation", "quel scenario",
        "quelle option", "je ne lancerai aucune modification",
        "voulez-vous", "souhaitez-vous", "voulez vous",
        "confirmez", "attendez confirmation",
        "attends votre confirmation", "attend votre confirmation",
        "attendre votre confirmation", "j'attends votre confirmation",
        "en attente de confirmation", "avant d'agir",
        "je peux :", "je peux\u00a0:",
    ]
    rep_str = str(reponse or "").lower()
    return any(sig in rep_str for sig in SIGNES_ECHEC)


def test_detecte_voulez_vous():
    assert _simuler_detection("Voulez-vous que je procede ?", "test")


def test_detecte_souhaitez_vous():
    assert _simuler_detection("Souhaitez-vous que je verifie ?", "test")


def test_detecte_attente_confirmation():
    assert _simuler_detection("J'attends votre confirmation avant d'agir", "test")


def test_ne_detecte_pas_succes_reel():
    assert not _simuler_detection("Fichier cree avec succes. Contenu: OK", "test")


def test_ne_detecte_pas_reponse_neutre():
    assert not _simuler_detection("Voici la liste des projets", "test")
