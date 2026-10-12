import unittest

from core.coordination_manager import CoordinationManager


class FauxLogger:
    def enregistrer(self, *args, **kwargs):
        pass


class FauxMissionManager:
    def __init__(self):
        self.statuts = []

    def mettre_a_jour_statut(self, mission_id, nouveau_statut):
        self.statuts.append((mission_id, nouveau_statut))


class TestSuperviserResultat(unittest.TestCase):
    def setUp(self):
        self.mm = FauxMissionManager()
        self.cm = CoordinationManager(self.mm, FauxLogger())

    def test_validation_invalide_bloque_la_mission(self):
        ok = self.cm.superviser_resultat(
            "C'est fait.", "m1", validation={"valide": False}
        )
        self.assertFalse(ok)
        self.assertEqual(self.mm.statuts, [("m1", "bloquee")])

    def test_validation_valide_termine_la_mission(self):
        ok = self.cm.superviser_resultat(
            "C'est fait.", "m1", validation={"valide": True}
        )
        self.assertTrue(ok)
        self.assertEqual(self.mm.statuts, [("m1", "terminee")])

    def test_sans_validation_bloque_la_mission(self):
        # Sans validation, pas de preuve : la mission est bloquee.
        ok = self.cm.superviser_resultat("C'est fait.", "m1", validation=None)
        self.assertFalse(ok)
        self.assertEqual(self.mm.statuts, [("m1", "bloquee")])

    def test_sans_mission_id_aucun_statut_change(self):
        self.cm.superviser_resultat(
            "C'est fait.", None, validation={"valide": False}
        )
        self.assertEqual(self.mm.statuts, [])


if __name__ == "__main__":
    unittest.main()
