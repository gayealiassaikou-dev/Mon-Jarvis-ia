"""Config pytest - desactive le budget guard sauf pour tests @llm."""
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def _disable_budget_guard(request):
    """Ne pas bloquer les tests sur le budget runtime (sauf @llm)."""
    # Les tests @llm veulent le vrai budget
    if request.node.get_closest_marker("llm"):
        yield
        return

    with patch("core.budget_guard.autorise", return_value=(True, "OK")):
        with patch("core.budget_guard.enregistrer_appel", return_value=None):
            yield
