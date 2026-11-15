"""Tests qui verifient qu'on ne brule pas de quota inutilement."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_budget_guard_structure():
    """Verifie que budget_guard expose les bonnes cles (pas l'etat runtime)."""
    from core import budget_guard
    etat = budget_guard.etat()
    for cle in ["appels", "tokens_estimes", "limite_appels", "limite_tokens", "restant_appels", "restant_tokens"]:
        assert cle in etat, f"Cle manquante: {cle}"
    assert etat["limite_appels"] > 0
    assert etat["limite_tokens"] > 0


def test_retry_force_conditionne():
    """Le retry force ne doit PAS etre declenche si la reponse contient du code/JSON."""
    src = open("core/subtask_executor.py", encoding="utf-8").read()
    # Verifier que la condition inclut _reponse_a_code
    assert "_reponse_a_code" in src, "Condition _reponse_a_code absente"
    assert "not _reponse_a_code" in src, "Retry force non conditionne"
