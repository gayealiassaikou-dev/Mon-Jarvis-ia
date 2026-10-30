import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.decision_engine import DecisionEngine

AGENTS = ["00_directeur_ia", "01_developpeur", "02_designer",
          "04_business", "05_architecte_ia", "09_securite_ia"]


class TestDecisionLocale(unittest.TestCase):
    def setUp(self):
        self.d = DecisionEngine.__new__(DecisionEngine)

    def agent(self, texte):
        r = self.d._decision_locale(texte, AGENTS)
        return r["agent"] if r else None

    def test_question_code_va_au_developpeur(self):
        self.assertEqual(self.agent("explique-moi ce bug python"), "01_developpeur")

    def test_design_va_au_designer(self):
        self.assertEqual(self.agent("propose une couleur pour le logo"), "02_designer")

    def test_actions_fichiers_laissees_a_l_ia(self):
        for t in ["supprime le fichier test", "crée un dossier python",
                  "écris un script python dans un fichier"]:
            self.assertIsNone(self.agent(t), t)

    def test_github_laisse_a_l_ia(self):
        self.assertIsNone(self.agent("montre mon code sur github"))

    def test_demande_vague_ou_vide_laissee_a_l_ia(self):
        for t in ["bonjour comment vas-tu", "", "   ", None]:
            self.assertIsNone(self.agent(t), repr(t))

    def test_demande_trop_longue_laissee_a_l_ia(self):
        self.assertIsNone(self.agent("python " * 100))

    def test_egalite_laissee_a_l_ia(self):
        self.assertIsNone(self.agent("code et design"))

    def test_format_de_retour(self):
        r = self.d._decision_locale("explique ce bug python", AGENTS)
        self.assertEqual(set(r), {"agent", "analyse", "outils_suggeres"})
        self.assertFalse(r["analyse"]["validation_requise"])
        self.assertEqual(r["outils_suggeres"], [])


if __name__ == "__main__":
    unittest.main()
