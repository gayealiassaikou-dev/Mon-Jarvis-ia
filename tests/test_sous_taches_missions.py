import os
import tempfile
import unittest
from unittest import mock

from core import mission_manager
from core.mission_manager import MissionManager


class TestSousTachesMissions(unittest.TestCase):

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)

        self.chemin = os.path.join(
            self.dossier.name, "data", "missions.json"
        )
        patcher = mock.patch.object(
            mission_manager, "CHEMIN_MISSIONS", self.chemin
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.mm = MissionManager()
        self.mission = self.mm.creer_mission(
            "Mission de test", "Objectif général"
        )

    def test_creer_sous_tache(self):
        sous_tache = self.mm.ajouter_sous_tache(
            self.mission["id"],
            "01_developpeur",
            "Analyser le code"
        )

        self.assertTrue(sous_tache["id"])
        self.assertEqual(sous_tache["agent"], "01_developpeur")
        self.assertEqual(sous_tache["objectif"], "Analyser le code")
        self.assertEqual(sous_tache["statut"], "nouvelle")
        self.assertIsNone(sous_tache["resultat"])
        self.assertEqual(sous_tache["dependances"], [])

    def test_sous_tache_conservee_apres_rechargement(self):
        sous_tache = self.mm.ajouter_sous_tache(
            self.mission["id"],
            "03_recherche",
            "Rechercher les informations"
        )

        retrouvees = self.mm.obtenir_sous_taches(self.mission["id"])

        self.assertEqual(len(retrouvees), 1)
        self.assertEqual(retrouvees[0]["id"], sous_tache["id"])

    def test_mettre_a_jour_statut_et_resultat(self):
        sous_tache = self.mm.ajouter_sous_tache(
            self.mission["id"],
            "01_developpeur",
            "Corriger un bug"
        )

        self.mm.mettre_a_jour_sous_tache(
            self.mission["id"],
            sous_tache["id"],
            "en_cours"
        )
        self.mm.mettre_a_jour_sous_tache(
            self.mission["id"],
            sous_tache["id"],
            "terminee",
            resultat="Correction vérifiée"
        )

        retrouvee = self.mm.obtenir_sous_taches(self.mission["id"])[0]
        self.assertEqual(retrouvee["statut"], "terminee")
        self.assertEqual(retrouvee["resultat"], "Correction vérifiée")

    def test_mission_introuvable(self):
        with self.assertRaises(ValueError):
            self.mm.ajouter_sous_tache(
                "mission_inconnue",
                "01_developpeur",
                "Tâche"
            )

    def test_sous_tache_introuvable(self):
        retour = self.mm.mettre_a_jour_sous_tache(
            self.mission["id"],
            "sous_tache_inconnue",
            "en_cours"
        )
        self.assertIn("introuvable", retour.lower())

    def test_statut_invalide_refuse(self):
        sous_tache = self.mm.ajouter_sous_tache(
            self.mission["id"],
            "01_developpeur",
            "Tâche de test"
        )

        retour = self.mm.mettre_a_jour_sous_tache(
            self.mission["id"],
            sous_tache["id"],
            "statut_inconnu"
        )

        self.assertIn("invalide", retour.lower())
        retrouvee = self.mm.obtenir_sous_taches(self.mission["id"])[0]
        self.assertEqual(retrouvee["statut"], "nouvelle")



    def test_dependance_inexistante_refusee(self):
        with self.assertRaises(ValueError):
            self.mm.ajouter_sous_tache(
                self.mission["id"], "01_developpeur", "Tache",
                dependances=["inexistante"]
            )

    def test_dependance_doit_etre_terminee_avant_demarrage(self):
        premiere = self.mm.ajouter_sous_tache(
            self.mission["id"], "03_recherche", "Rechercher"
        )
        seconde = self.mm.ajouter_sous_tache(
            self.mission["id"], "01_developpeur", "Developper",
            dependances=[premiere["id"]]
        )

        retour = self.mm.mettre_a_jour_sous_tache(
            self.mission["id"], seconde["id"], "en_cours"
        )
        self.assertIn("dependances", retour.lower())
        self.assertEqual(
            self.mm.obtenir_sous_taches(self.mission["id"])[1]["statut"],
            "nouvelle"
        )

        self.mm.mettre_a_jour_sous_tache(
            self.mission["id"], premiere["id"], "en_cours"
        )
        self.mm.mettre_a_jour_sous_tache(
            self.mission["id"], premiere["id"], "terminee",
            resultat="Recherche terminee"
        )
        retour = self.mm.mettre_a_jour_sous_tache(
            self.mission["id"], seconde["id"], "en_cours"
        )
        self.assertIn("en_cours", retour)

    def test_type_dependances_invalide_refuse(self):
        with self.assertRaises(ValueError):
            self.mm.ajouter_sous_tache(
                self.mission["id"], "01_developpeur", "Tache",
                dependances={}
            )

    def test_ancienne_mission_sans_sous_taches_compatible(self):
        donnees = self.mm._charger()
        donnees["missions"][0].pop("sous_taches", None)
        self.mm._sauvegarder(donnees)

        sous_tache = self.mm.ajouter_sous_tache(
            self.mission["id"], "01_developpeur", "Tache compatible"
        )
        self.assertTrue(sous_tache["id"])

if __name__ == "__main__":
    unittest.main()
