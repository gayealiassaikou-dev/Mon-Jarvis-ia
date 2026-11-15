"""Config pytest - desactive le budget guard pour les tests."""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _disable_budget_guard():
    """Ne pas bloquer les tests sur le budget runtime."""
    with patch("core.budget_guard.autorise", return_value=(True, "OK")):
        with patch("core.budget_guard.enregistrer_appel", return_value=None):
            yield
