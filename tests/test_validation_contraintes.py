import unittest
from unittest.mock import patch

import core.ai_engine as moteur

FAUX_OUTILS = [{
    "type": "function",
    "function": {
        "name": "outil_test",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["a", "b"]},
                "nom": {"type": "string", "minLength": 2, "maxLength": 5},
                "age": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": [],
        },
    },
}]


class TestContraintesSchema(unittest.TestCase):
    def setUp(self):
        self.moteur = object.__new__(moteur.AIEngine)
        patcher = patch.object(moteur, "OUTILS", FAUX_OUTILS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def verifier(self, arguments):
        return self.moteur._valider_arguments_outil("outil_test", arguments)

    def test_valeurs_valides(self):
        ok, _ = self.verifier({"mode": "a", "nom": "abc", "age": 5})
        self.assertTrue(ok)

    def test_enum_refuse(self):
        ok, _ = self.verifier({"mode": "z"})
        self.assertFalse(ok)

    def test_minlength_refuse(self):
        ok, _ = self.verifier({"nom": "a"})
        self.assertFalse(ok)

    def test_maxlength_refuse(self):
        ok, _ = self.verifier({"nom": "abcdef"})
        self.assertFalse(ok)

    def test_minimum_refuse(self):
        ok, _ = self.verifier({"age": 0})
        self.assertFalse(ok)

    def test_maximum_refuse(self):
        ok, _ = self.verifier({"age": 11})
        self.assertFalse(ok)

    def test_limites_acceptees(self):
        for arguments in ({"nom": "ab"}, {"nom": "abcde"},
                          {"age": 1}, {"age": 10}):
            ok, _ = self.verifier(arguments)
            self.assertTrue(ok, arguments)


if __name__ == "__main__":
    unittest.main()
