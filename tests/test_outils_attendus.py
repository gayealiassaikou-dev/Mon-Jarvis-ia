import unittest

from core.validation_manager import ValidationManager


class FauxLogger:
    def enregistrer(self, *args, **kwargs):
        pass


REPONSE = "J'ai cree le depot comme demande."

RESULTAT_OK = {
    "outil": "github_creer_repo",
    "statut": "succes",
    "disponible": True,
    "autorise": True,
    "arguments_valides": True,
    "execute": True,
    "resultat": "Depot cree",
    "verification": {"verifie": True, "details": "ok"},
}


class TestOutilsAttendus(unittest.TestCase):
    def setUp(self):
        self.vm = ValidationManager(FauxLogger())

    def test_mission_outils_attendus_liste_vide_rejetee(self):
        v = self.vm.valider(REPONSE, "m1", [], outils_attendus=True)
        self.assertFalse(v["valide"])

    def test_mission_outils_attendus_resultat_prouve_acceptee(self):
        v = self.vm.valider(REPONSE, "m1", [RESULTAT_OK], outils_attendus=True)
        self.assertTrue(v["valide"])

    def test_mission_sans_outils_attendus_acceptee(self):
        v = self.vm.valider(REPONSE, "m1", [], outils_attendus=False)
        self.assertTrue(v["valide"])

    def test_conversation_sans_mission_inchangee(self):
        v = self.vm.valider(REPONSE, None, [], outils_attendus=True)
        self.assertTrue(v["valide"])

    def test_appel_ancien_sans_parametre_inchange(self):
        v = self.vm.valider(REPONSE, "m1", [])
        self.assertTrue(v["valide"])


if __name__ == "__main__":
    unittest.main()
