import unittest
from core.ai_engine import AIEngine


class TestVerificationResultats(unittest.TestCase):
    def test_outil_sans_verification_specifique_non_confirme(self):
        moteur = AIEngine()
        verification = moteur._verifier_resultat_outil(
            "outil_inconnu", {}, "Action réussie"
        )
        self.assertIsNone(verification["verifie"])


    def test_lecture_retourne_none_non_verifie(self):
        moteur = AIEngine()
        verification = moteur._verifier_resultat_outil(
            "lire_fichier", {"chemin": "exemple.txt"}, None
        )
        self.assertFalse(verification["verifie"])


if __name__ == "__main__":
    unittest.main()
