import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.mission_manager import MissionManager
from core.validation_manager import ValidationManager
from core.orchestrator import Orchestrator


class FauxAIEngine:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.derniers_resultats_outils = []
        self.appels = []

    def demander(self, message, contexte="", outils_autorises=None,
                 mode_action=False, **kwargs):
        self.appels.append({
            "message": message,
            "outils": outils_autorises,
            "mode_action": mode_action,
            "origine": kwargs.get("message_utilisateur_origine"),
        })
        reponse, resultats = self.reponses.pop(0)
        self.derniers_resultats_outils = resultats
        return reponse


class TestOrchestratorExecution(unittest.TestCase):

    def setUp(self):
        self.temporaire = tempfile.TemporaryDirectory()
        chemin = os.path.join(self.temporaire.name, "missions.json")

        patcher = patch("core.mission_manager.CHEMIN_MISSIONS", chemin)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.missions = MissionManager()
        self.agents = Mock()
        self.agents.agents = {
            "01_developpeur": "Agent developpeur",
            "03_recherche": "Agent recherche",
            "08_testeur_ia": "Agent testeur",
        }

        self.logger = Mock()
        self.validation = ValidationManager(self.logger)
        self.decision = Mock()
        self.decision.obtenir_contexte_agent.side_effect = (
            lambda agent: self.agents.agents[agent]
        )

        self.addCleanup(self.temporaire.cleanup)

    def creer_orchestrateur(self, reponses):
        self.ai = FauxAIEngine(reponses)
        return Orchestrator(
            self.missions,
            self.agents,
            self.ai,
            self.validation,
            self.decision,
            self.logger,
        )

    def test_analyse_sans_outils(self):
        orchestrateur = self.creer_orchestrateur([
            ("Analyse terminee avec succes.", [])
        ])

        resultat = orchestrateur.executer(
            "Analyser un sujet",
            plan={
                "nom": "Analyse",
                "sous_taches": [{
                    "agent": "03_recherche",
                    "objectif": "Analyser les informations",
                    "dependances": [],
                    "action_requise": False,
                }],
            },
        )

        self.assertTrue(resultat["succes"])
        self.assertEqual(self.ai.appels[0]["outils"], [])
        self.assertFalse(self.ai.appels[0]["mode_action"])

        mission = self.missions.obtenir_mission(resultat["mission_id"])
        self.assertEqual(mission["statut"], "terminee")
        self.assertEqual(mission["sous_taches"][0]["statut"], "terminee")

    def test_action_reussie_avec_preuve(self):
        preuve = {
            "outil": "lire_fichier",
            "statut": "succes",
            "disponible": True,
            "autorise": True,
            "arguments_valides": True,
            "execute": True,
            "resultat": "Fichier lu correctement",
            "verification": {
                "verifie": True,
                "details": "Lecture confirmee",
            },
        }

        orchestrateur = self.creer_orchestrateur([
            ("Le fichier a ete lu et verifie.", [preuve])
        ])

        resultat = orchestrateur.executer(
            "Lire un fichier",
            plan={
                "nom": "Lecture",
                "sous_taches": [{
                    "agent": "01_developpeur",
                    "objectif": "Lire le fichier demande",
                    "dependances": [],
                    "action_requise": True,
                }],
            },
        )

        self.assertTrue(resultat["succes"])
        self.assertTrue(self.ai.appels[0]["mode_action"])
        self.assertEqual(self.ai.appels[0]["origine"], "Lire un fichier")
        self.assertIn("lire_fichier", self.ai.appels[0]["outils"])

        mission = self.missions.obtenir_mission(resultat["mission_id"])
        self.assertEqual(mission["statut"], "terminee")
        self.assertEqual(mission["sous_taches"][0]["statut"], "terminee")

    def test_action_sans_preuve_bloque_les_agents_suivants(self):
        orchestrateur = self.creer_orchestrateur([
            ("Action effectuee.", [])
        ])

        resultat = orchestrateur.executer(
            "Effectuer puis analyser",
            plan={
                "nom": "Mission bloquee",
                "sous_taches": [
                    {
                        "agent": "01_developpeur",
                        "objectif": "Effectuer une action",
                        "dependances": [],
                        "action_requise": True,
                    },
                    {
                        "agent": "03_recherche",
                        "objectif": "Analyser le resultat",
                        "dependances": [0],
                        "action_requise": False,
                    },
                ],
            },
        )

        self.assertFalse(resultat["succes"])
        self.assertEqual(len(self.ai.appels), 1)

        mission = self.missions.obtenir_mission(resultat["mission_id"])
        self.assertEqual(mission["statut"], "bloquee")
        self.assertEqual(mission["sous_taches"][0]["statut"], "bloquee")
        self.assertEqual(mission["sous_taches"][1]["statut"], "nouvelle")


if __name__ == "__main__":
    unittest.main()
