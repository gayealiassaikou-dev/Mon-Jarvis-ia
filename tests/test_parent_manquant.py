import os
import tempfile
import unittest
from unittest.mock import patch

from core import tools


class TestParentManquant(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = self.temp.name
        self.proteges_fichiers = [
            os.path.join(self.racine, ".env"),
            os.path.join(self.racine, ".git"),
        ]
        self.proteges_dossiers = [
            os.path.join(self.racine, "core"),
        ]
        self.patch_racine = patch.object(
            tools, "DOSSIER_AUTORISE", self.racine
        )
        self.patch_fichiers = patch.object(
            tools, "FICHIERS_PROTEGES", self.proteges_fichiers
        )
        self.patch_dossiers = patch.object(
            tools, "DOSSIERS_PROTEGES", self.proteges_dossiers
        )
        self.patch_racine.start()
        self.patch_fichiers.start()
        self.patch_dossiers.start()

    def tearDown(self):
        self.patch_dossiers.stop()
        self.patch_fichiers.stop()
        self.patch_racine.stop()
        self.temp.cleanup()

    def test_cree_un_seul_parent_manquant(self):
        os.mkdir(os.path.join(self.racine, "projet"))
        resultat = tools.creer_parent_manquant_pour_ecriture(
            "projet/nouveau/fichier.txt"
        )
        self.assertTrue(resultat)
        self.assertTrue(os.path.isdir(
            os.path.join(self.racine, "projet", "nouveau")
        ))

    def test_refuse_plusieurs_niveaux_manquants(self):
        resultat = tools.creer_parent_manquant_pour_ecriture(
            "absent/nouveau/fichier.txt"
        )
        self.assertFalse(resultat)
        self.assertFalse(os.path.exists(
            os.path.join(self.racine, "absent")
        ))

    def test_refuse_chemin_exterieur(self):
        resultat = tools.creer_parent_manquant_pour_ecriture(
            os.path.join(tempfile.gettempdir(), "exterieur", "f.txt")
        )
        self.assertFalse(resultat)

    def test_refuse_dossier_protege(self):
        resultat = tools.creer_parent_manquant_pour_ecriture(
            "core/fichier.txt"
        )
        self.assertFalse(resultat)
        self.assertFalse(os.path.exists(
            os.path.join(self.racine, "core")
        ))


if __name__ == "__main__":
    unittest.main()
