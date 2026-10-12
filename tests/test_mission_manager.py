import os
import tempfile
import unittest
from unittest import mock

from core import mission_manager
from core.mission_manager import MissionManager


class TestMissionManager(unittest.TestCase):
    def setUp(self):
        # Fichier de missions temporaire : data/missions.json n'est jamais touche.
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.chemin = os.path.join(self.dossier.name, "data", "missions.json")
        patcher = mock.patch.object(mission_manager, "CHEMIN_MISSIONS", self.chemin)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mm = MissionManager()

    def _statut(self, mission_id):
        for m in self.mm._charger()["missions"]:
            if m["id"] == mission_id:
                return m["statut"]
        return None

    def test_utilise_un_fichier_temporaire(self):
        self.assertEqual(self.mm.chemin, self.chemin)
        self.assertTrue(os.path.exists(self.chemin))

    def test_creer_mission_statut_nouvelle(self):
        m = self.mm.creer_mission("Test", "Objectif")
        self.assertEqual(m["statut"], "nouvelle")
        self.assertEqual(self._statut(m["id"]), "nouvelle")

    def test_priorite_invalide_devient_normale(self):
        m = self.mm.creer_mission("Test", priorite="urgentissime")
        self.assertEqual(m["priorite"], "normale")

    def test_nouvelle_vers_terminee_refusee(self):
        m = self.mm.creer_mission("Test")
        retour = self.mm.mettre_a_jour_statut(m["id"], "terminee")
        self.assertIn("refusee", retour)
        self.assertEqual(self._statut(m["id"]), "nouvelle")

    def test_cycle_normal_jusqu_a_terminee(self):
        m = self.mm.creer_mission("Test")
        self.mm.mettre_a_jour_statut(m["id"], "en_cours")
        self.mm.mettre_a_jour_statut(m["id"], "terminee")
        self.assertEqual(self._statut(m["id"]), "terminee")

    def test_terminee_est_definitive(self):
        m = self.mm.creer_mission("Test")
        self.mm.mettre_a_jour_statut(m["id"], "en_cours")
        self.mm.mettre_a_jour_statut(m["id"], "terminee")
        retour = self.mm.mettre_a_jour_statut(m["id"], "en_cours")
        self.assertIn("refusee", retour)
        self.assertEqual(self._statut(m["id"]), "terminee")

    def test_bloquee_peut_reprendre(self):
        m = self.mm.creer_mission("Test")
        self.mm.mettre_a_jour_statut(m["id"], "en_cours")
        self.mm.mettre_a_jour_statut(m["id"], "bloquee")
        self.mm.mettre_a_jour_statut(m["id"], "en_cours")
        self.assertEqual(self._statut(m["id"]), "en_cours")

    def test_statut_invalide(self):
        m = self.mm.creer_mission("Test")
        retour = self.mm.mettre_a_jour_statut(m["id"], "inconnu")
        self.assertIn("invalide", retour.lower())
        self.assertEqual(self._statut(m["id"]), "nouvelle")

    def test_mission_introuvable(self):
        retour = self.mm.mettre_a_jour_statut("xxxxxxxx", "en_cours")
        self.assertIn("introuvable", retour)

    def test_meme_statut_ne_change_rien(self):
        m = self.mm.creer_mission("Test")
        retour = self.mm.mettre_a_jour_statut(m["id"], "nouvelle")
        self.assertIn("deja", retour)


if __name__ == "__main__":
    unittest.main()
