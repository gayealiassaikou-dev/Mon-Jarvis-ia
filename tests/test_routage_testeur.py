import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from core.agent_permissions import (
    obtenir_outils_autorises,
    filtrer_outils,
)
from core.decision_engine import DecisionEngine


class TestRoutageTesteur(unittest.TestCase):
    def test_decider_conserve_le_testeur_et_son_outil(self):
        moteur = object.__new__(DecisionEngine)
        moteur.agent_manager = Mock()
        moteur.agent_manager.agents = {
            "00_directeur_ia": "Directeur",
            "08_testeur_ia": "Testeur",
        }
        moteur.ai_engine = Mock()
        moteur.ai_engine.demander.return_value = json.dumps({
            "agent": "08_testeur_ia",
            "difficulte": "faible",
            "risques": "faible",
            "validation_requise": False,
            "resume": "Exécuter les tests",
            "outils_suggeres": ["executer_tests_python"],
        })
        moteur.outils_disponibles = [
            "executer_tests_python",
            "supprimer_fichier",
        ]

        resultat = moteur.decider("Lance les tests du projet")

        self.assertEqual(resultat["agent"], "08_testeur_ia")
        self.assertEqual(
            resultat["outils_suggeres"],
            ["executer_tests_python"],
        )
        moteur.ai_engine.demander.assert_called_once()

    def test_recherche_instructions_propose_localisation_et_lecture(self):
        moteur = object.__new__(DecisionEngine)
        moteur.agent_manager = Mock()
        moteur.agent_manager.agents = {
            "00_directeur_ia": "Directeur",
            "03_recherche": "Chercheur",
        }
        moteur.ai_engine = Mock()
        moteur.ai_engine.demander.return_value = json.dumps({
            "agent": "03_recherche",
            "difficulte": "faible",
            "risques": "faible",
            "validation_requise": False,
            "resume": "Lire les instructions de l agent de recherche",
            "outils_suggeres": [],
        })
        moteur.outils_disponibles = [
            "lister_fichiers",
            "lire_fichier",
            "rechercher_web",
        ]

        resultat = moteur.decider(
            "Ouvre le dossier agent de recherche et lis-moi ses instructions."
        )

        self.assertEqual(resultat["agent"], "03_recherche")
        self.assertIn("lister_fichiers", resultat["outils_suggeres"])
        self.assertIn("lire_fichier", resultat["outils_suggeres"])

    @patch("subprocess.run")
    def test_resultat_echec_tests_est_signale(self, lancer):
        from core.tools import executer_tests_python

        lancer.return_value = subprocess.CompletedProcess(
            args=["python", "-m", "unittest"],
            returncode=1,
            stdout="Un test a échoué.",
            stderr="AssertionError",
        )
        with patch("os.path.isdir", return_value=True):
            resultat = executer_tests_python()

        self.assertIn("ÉCHEC", resultat)
        self.assertIn("AssertionError", resultat)

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("python", 90))
    def test_delai_depasse_est_signale(self, lancer):
        from core.tools import executer_tests_python

        with patch("os.path.isdir", return_value=True):
            resultat = executer_tests_python()

        self.assertIn("délai maximal de 90 secondes dépassé", resultat)

    def test_testeur_est_autorise_a_lancer_les_tests(self):
        outils = obtenir_outils_autorises("08_testeur_ia")
        self.assertIn("executer_tests_python", outils)

    def test_developpeur_ne_peut_pas_lancer_directement_les_tests(self):
        outils = obtenir_outils_autorises("01_developpeur")
        self.assertNotIn("executer_tests_python", outils)

    def test_filtrage_respecte_les_permissions(self):
        outils = filtrer_outils(
            "08_testeur_ia",
            ["executer_tests_python", "supprimer_fichier"],
        )
        self.assertEqual(outils, ["executer_tests_python"])

    def test_coherence_reserve_l_outil_au_testeur(self):
        moteur = object.__new__(DecisionEngine)
        verifier = moteur._verifier_coherence_agent_outils
        self.assertTrue(
            verifier("08_testeur_ia", ["executer_tests_python"])
        )
        self.assertFalse(
            verifier("01_developpeur", ["executer_tests_python"])
        )
        self.assertTrue(
            verifier("00_directeur_ia", ["executer_tests_python"])
        )


    def test_interpretation_argot_transmise_sans_modifier_demande(self):
        moteur = object.__new__(DecisionEngine)
        moteur.agent_manager = Mock()
        moteur.agent_manager.agents = {
            "00_directeur_ia": "Directeur",
        }
        moteur.ai_engine = Mock()
        moteur.ai_engine.demander.return_value = json.dumps({
            "agent": "00_directeur_ia",
            "difficulte": "faible",
            "risques": "aucun",
            "validation_requise": False,
            "resume": "Vérifier la compréhension de la demande",
            "outils_suggeres": [],
        })
        moteur.outils_disponibles = []

        demande = "T'as capté ?"
        resultat = moteur.decider(demande)

        self.assertEqual(resultat["agent"], "00_directeur_ia")
        moteur.ai_engine.demander.assert_called_once()

        args, kwargs = moteur.ai_engine.demander.call_args
        prompt = args[0]

        self.assertIn("Question informelle signifiant généralement", prompt)
        self.assertIn(f'Demande utilisateur : "{demande}"', prompt)
        self.assertEqual(kwargs.get("outils_autorises"), [])
        self.assertIs(kwargs.get("mode_action"), False)


if __name__ == "__main__":
    unittest.main()
