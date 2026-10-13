import unittest

from core.validation_manager import ValidationManager


class LoggerMemoire:
    def __init__(self):
        self.messages = []

    def enregistrer(self, message, *args, **kwargs):
        self.messages.append(str(message))


class TestRejetExtrait(unittest.TestCase):
    def test_extrait_de_la_vraie_cause_est_journalise(self):
        logger = LoggerMemoire()
        vm = ValidationManager(logger)
        reponse = (
            "Erreur IA apres execution d'une action avec groq : "
            "HTTPError: 400 tool_use_failed. Fallback annule."
        )
        v = vm.valider(reponse, "m1")
        self.assertFalse(v["valide"])
        self.assertTrue(any("tool_use_failed" in m for m in logger.messages))


if __name__ == "__main__":
    unittest.main()
