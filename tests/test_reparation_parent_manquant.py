import os
import tempfile
import unittest
from unittest.mock import patch

import core.tools as outils
import core.ai_engine as moteur


class TestReparationParentManquant(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = self.temp.name
        os.mkdir(os.path.join(self.racine, "projet"))

        self.patch_racine = patch.object(
            outils, "DOSSIER_AUTORISE", self.racine
        )
        self.patch_racine.start()

        self.patch_fichiers = patch.object(
            outils,
            "FICHIERS_PROTEGES",
            [
                os.path.join(self.racine, ".env"),
                os.path.join(self.racine, ".git"),
            ],
        )
        self.patch_fichiers.start()

        self.patch_dossiers = patch.object(
            outils,
            "DOSSIERS_PROTEGES",
            [os.path.join(self.racine, "core")],
        )
        self.patch_dossiers.start()

        self.moteur = moteur.AIEngine()
        self.moteur.derniers_resultats_outils = []
        self.moteur.outils_autorises = ["ecrire_fichier"]

    def tearDown(self):
        self.patch_dossiers.stop()
        self.patch_fichiers.stop()
        self.patch_racine.stop()
        self.temp.cleanup()

    def test_repare_parent_manquant_et_verifie_ecriture(self):
        arguments = {
            "chemin": "projet/nouveau/fichier.txt",
            "contenu": "Samba Sarr fonctionne",
        }

        premier_resultat = self.moteur._executer_outil(
            "ecrire_fichier", arguments
        )
        entree_echec = self.moteur.derniers_resultats_outils[-1]

        self.assertIsInstance(premier_resultat, str)
        self.assertEqual(entree_echec.get("statut"), "echec_execution")
        self.assertIn(
            "dossier parent",
            str(entree_echec.get("resultat", "")).lower(),
        )

        repare = self.moteur.rejouer_outil_echoue(
            "ecrire_fichier", ["ecrire_fichier"]
        )

        chemin = os.path.join(
            self.racine, "projet", "nouveau", "fichier.txt"
        )
        self.assertTrue(repare)
        self.assertTrue(os.path.isfile(chemin))

        with open(chemin, "r", encoding="utf-8") as fichier:
            self.assertEqual(
                fichier.read(), "Samba Sarr fonctionne"
            )

        resultats = self.moteur.derniers_resultats_outils
        self.assertTrue(
            any(
                resultat.get("statut") == "succes"
                and resultat.get("verification", {}).get("verifie") is True
                for resultat in resultats
                if isinstance(resultat, dict)
            )
        )

    def test_ne_cree_pas_plusieurs_niveaux_manquants(self):
        resultat = outils.creer_parent_manquant_pour_ecriture(
            "absent/nouveau/fichier.txt"
        )

        self.assertFalse(resultat)
        self.assertFalse(
            os.path.exists(os.path.join(self.racine, "absent"))
        )


if __name__ == "__main__":
    unittest.main()
