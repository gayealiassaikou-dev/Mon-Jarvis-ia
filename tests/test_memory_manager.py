import unittest
from core.memory_manager import MemoryManager


class TestRechercheSouvenirs(unittest.TestCase):
    def setUp(self):
        self.manager = MemoryManager.__new__(MemoryManager)
        self.manager.memoire = {
            "projets": [
                "Le projet Sam Sarr utilise Python",
                "Le projet Halibourer aide à retrouver des enfants"
            ],
            "decisions": [
                "Utiliser une architecture hybride pour Sam Sarr"
            ],
            "preferences": [
                "Préférer les commandes courtes et progressives"
            ],
            "connaissances": [
                "Python permet de créer des applications"
            ],
            "erreurs": [
                "Erreur de connexion au fournisseur"
            ]
        }

    def test_recherche_insensible_aux_accents(self):
        resultat = self.manager.rechercher_souvenir("preferer")
        self.assertIn("commandes courtes", resultat)

    def test_recherche_insensible_aux_majuscules(self):
        resultat = self.manager.rechercher_souvenir("sam sarr")
        self.assertIn("Sam Sarr", resultat)

    def test_recherche_sans_resultat(self):
        resultat = self.manager.rechercher_souvenir("astronomie")
        self.assertIn("Aucune information", resultat)


if __name__ == "__main__":
    unittest.main()
