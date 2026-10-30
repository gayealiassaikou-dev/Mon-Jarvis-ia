import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.ai_router as ai_router

CLASSES = [c for c in vars(ai_router).values()
           if isinstance(c, type) and hasattr(c, "bloquer_temporairement")]


class FauxMoteur:
    providers = {"groq": {"priorite": 1}}
    action_engagee = False

    def _demander_groq(self, *args, **kwargs):
        raise Exception("429 quota depasse")


class TestMessageEchecTotal(unittest.TestCase):
    def setUp(self):
        self.routeur = CLASSES[0](FauxMoteur())

    def test_echec_normal_garde_le_prefixe_et_les_capacites(self):
        r = self.routeur.demander("bonjour")
        self.assertTrue(r.startswith("Toutes les IA sont indisponibles"))
        self.assertIn("429", r)
        self.assertIn("sans IA", r)

    def test_fournisseurs_bloques_donnent_une_explication(self):
        self.routeur.bloquer_temporairement("groq")
        r = self.routeur.demander("bonjour")
        self.assertTrue(r.startswith("Toutes les IA sont indisponibles"))
        self.assertIn("temporairement bloqués", r)
        self.assertIn("sans IA", r)


if __name__ == "__main__":
    unittest.main()
