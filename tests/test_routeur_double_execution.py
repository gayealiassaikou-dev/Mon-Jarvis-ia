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
        ordre = self.moteur.router.fournisseurs
        premier, second = ordre[:2]
        self.installer({
            premier: self.agit_puis_plante(premier, "429 quota"),
            second: self.repond(second, "reponse suivante"),
        })
        reponse = self.lancer()
        self.assertEqual(self.appels_fournisseurs, [premier])
        self.assertEqual(self.appels_outil, [self.chemin])
        self.assertTrue(reponse.startswith("Erreur IA"))
    def test_fallback_si_echec_avant_action(self):
        ordre = self.moteur.router.fournisseurs
        premier, second = ordre[:2]
        self.installer({
            premier: self.plante(premier, "erreur reseau"),
            second: self.repond(second, "reponse suivante"),
        })
        reponse = self.lancer()
        self.assertEqual(self.appels_fournisseurs, [premier, second])
        self.assertEqual(self.appels_outil, [])
        self.assertEqual(reponse, "reponse suivante")
    def test_toutes_indisponibles(self):
        self.installer({})
        reponse = self.lancer()
        self.assertEqual(
            self.appels_fournisseurs, self.moteur.router.fournisseurs
        )
        self.assertEqual(self.appels_outil, [])
        self.assertTrue(
            reponse.startswith("Toutes les IA sont indisponibles")
        )
    def test_quota_bloque_le_fournisseur(self):
        ordre = self.moteur.router.fournisseurs
        premier, second = ordre[:2]
        self.installer({
            premier: self.plante(premier, "429 quota"),
            second: self.repond(second, "reponse suivante"),
        })
        self.lancer()
        self.assertIn(premier, self.moteur.router.indisponibles)
        self.appels_fournisseurs.clear()
        self.lancer()
        self.assertNotIn(premier, self.appels_fournisseurs)

    def test_ordre_respecte_les_priorites_configurees(self):
        configuration = {
            "mistral": {"priorite": 1},
            "openrouter": {"priorite": 2},
            "groq": {"priorite": 3},
            "gemini": {"priorite": 4},
        }
        with patch.object(self.moteur, "providers", configuration):
            routeur = moteur.AIRouter(self.moteur)
        self.assertEqual(
            routeur.fournisseurs,
            ["mistral", "openrouter", "groq", "gemini"],
        )

if __name__ == "__main__":
    unittest.main()
