import unittest
from unittest import mock

from core.orchestrator import Orchestrator


class TestOrchestrator(unittest.TestCase):

    def setUp(self):
        self.agents = {
            "01_developpeur": "Instructions developpeur",
            "03_recherche": "Instructions recherche",
            "08_testeur_ia": "Instructions testeur",
            "00_directeur_ia": "Instructions directeur",
            "11_gestionnaire_outils_ia": "Instructions outils",
        }

        self.orchestrator = Orchestrator(
            mission_manager=mock.Mock(),
            agent_manager=mock.Mock(agents=self.agents),
            ai_engine=mock.Mock(),
            validation_manager=mock.Mock(),
            decision_engine=mock.Mock(),
        )

    def plan_simple(self):
        return {
            "nom": "Mission de test",
            "sous_taches": [
                {
                    "agent": "03_recherche",
                    "objectif": "Analyser les informations",
                    "dependances": [],
                    "action_requise": False,
                }
            ],
        }

    def test_plan_valide(self):
        resultat = self.orchestrator.valider_plan(self.plan_simple())
        self.assertEqual(len(resultat["sous_taches"]), 1)
        self.assertEqual(
            resultat["sous_taches"][0]["agent"], "03_recherche"
        )

    def test_refuse_agent_inconnu(self):
        plan = self.plan_simple()
        plan["sous_taches"][0]["agent"] = "99_inconnu"

        with self.assertRaises(ValueError):
            self.orchestrator.valider_plan(plan)

    def test_refuse_directeur(self):
        plan = self.plan_simple()
        plan["sous_taches"][0]["agent"] = "00_directeur_ia"

        with self.assertRaises(ValueError):
            self.orchestrator.valider_plan(plan)

    def test_refuse_gestionnaire_outils(self):
        plan = self.plan_simple()
        plan["sous_taches"][0]["agent"] = "11_gestionnaire_outils_ia"

        with self.assertRaises(ValueError):
            self.orchestrator.valider_plan(plan)

    def test_refuse_dependance_invalide(self):
        plan = self.plan_simple()
        plan["sous_taches"].append({
            "agent": "01_developpeur",
            "objectif": "Traiter le resultat",
            "dependances": [5],
            "action_requise": False,
        })

        with self.assertRaises(ValueError):
            self.orchestrator.valider_plan(plan)

    def test_refuse_plus_de_huit_sous_taches(self):
        plan = {
            "nom": "Trop de taches",
            "sous_taches": [
                {
                    "agent": "03_recherche",
                    "objectif": f"Analyser element {i}",
                    "dependances": [],
                    "action_requise": False,
                }
                for i in range(9)
            ],
        }

        with self.assertRaises(ValueError):
            self.orchestrator.valider_plan(plan)

    def test_refuse_json_invalide(self):
        with self.assertRaises(ValueError):
            self.orchestrator._extraire_json("aucun JSON ici")

    def test_extrait_json_entoure_de_texte(self):
        resultat = self.orchestrator._extraire_json(
            'Voici le plan : {"sous_taches": []}'
        )
        self.assertEqual(resultat, {"sous_taches": []})


if __name__ == "__main__":
    unittest.main()
