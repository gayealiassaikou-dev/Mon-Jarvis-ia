import os
import tempfile
import unittest
from unittest.mock import patch

import core.ai_engine as moteur

FOURNISSEURS = ["mistral", "openrouter", "groq", "gemini"]


class TestRouteurDoubleExecution(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.chemin = os.path.join(tmp.name, "dossier_test")
        self.moteur = moteur.AIEngine()
        self.appels_outil = []
        self.appels_fournisseurs = []

    def outil_qui_cree(self, chemin):
        self.appels_outil.append(chemin)
        os.makedirs(chemin, exist_ok=True)
        return "Dossier cree : " + chemin

    def agit_puis_plante(self, nom, erreur):
        def faux(message, contexte="", historique=None):
            self.appels_fournisseurs.append(nom)
            self.moteur._executer_outil("creer_dossier", {"chemin": self.chemin})
            raise Exception(erreur)
        return faux

    def plante(self, nom, erreur):
        def faux(message, contexte="", historique=None):
            self.appels_fournisseurs.append(nom)
            raise Exception(erreur)
        return faux

    def repond(self, nom, texte):
        def faux(message, contexte="", historique=None):
            self.appels_fournisseurs.append(nom)
            return texte
        return faux

    def installer(self, faux_par_nom):
        for nom in FOURNISSEURS:
            faux = faux_par_nom.get(nom) or self.plante(nom, "erreur de test")
            p = patch.object(self.moteur, "_demander_" + nom, faux)
            p.start()
            self.addCleanup(p.stop)

    def lancer(self):
        with patch.dict(moteur.FONCTIONS_DISPONIBLES,
                        {"creer_dossier": self.outil_qui_cree}):
            return self.moteur.demander(
                "cree un dossier",
                outils_autorises=["creer_dossier"],
                mode_action=True,
            )

    def test_pas_de_fallback_apres_action(self):
        self.installer({
            "mistral": self.agit_puis_plante("mistral", "429 quota"),
            "openrouter": self.repond("openrouter", "reponse openrouter"),
        })
        reponse = self.lancer()
        self.assertEqual(self.appels_fournisseurs, ["mistral"])
        self.assertEqual(self.appels_outil, [self.chemin])
        self.assertTrue(reponse.startswith("Erreur IA"))

    def test_fallback_si_echec_avant_action(self):
        self.installer({
            "mistral": self.plante("mistral", "erreur reseau"),
            "openrouter": self.repond("openrouter", "reponse openrouter"),
        })
        reponse = self.lancer()
        self.assertEqual(self.appels_fournisseurs, ["mistral", "openrouter"])
        self.assertEqual(self.appels_outil, [])
        self.assertEqual(reponse, "reponse openrouter")

    def test_toutes_indisponibles(self):
        self.installer({})
        reponse = self.lancer()
        self.assertEqual(self.appels_fournisseurs, FOURNISSEURS)
        self.assertEqual(self.appels_outil, [])
        self.assertTrue(reponse.startswith("Toutes les IA sont indisponibles"))

    def test_quota_bloque_le_fournisseur(self):
        self.installer({
            "mistral": self.plante("mistral", "429 quota"),
            "openrouter": self.repond("openrouter", "reponse openrouter"),
        })
        self.lancer()
        self.assertIn("mistral", self.moteur.router.indisponibles)
        self.appels_fournisseurs.clear()
        self.lancer()
        self.assertNotIn("mistral", self.appels_fournisseurs)


if __name__ == "__main__":
    unittest.main()
