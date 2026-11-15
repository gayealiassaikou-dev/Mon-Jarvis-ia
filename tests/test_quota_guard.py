"""Tests qui verifient qu'on ne brule pas de quota inutilement."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_budget_bas_avant_test_reel():
    """Avant tout test reel, verifier qu'il reste du budget."""
    from core import budget_guard
    etat = budget_guard.etat()
    restant = etat["restant_appels"]
    assert restant > 50, f"Budget trop bas pour test reel: {restant} restants"


def test_retry_force_conditionne():
    """Le retry force ne doit PAS etre declenche si la reponse contient du code/JSON."""
    src = open("core/subtask_executor.py", encoding="utf-8").read()
    # Verifier que la condition inclut _reponse_a_code
    assert "_reponse_a_code" in src, "Condition _reponse_a_code absente"
    assert "not _reponse_a_code" in src, "Retry force non conditionne"
