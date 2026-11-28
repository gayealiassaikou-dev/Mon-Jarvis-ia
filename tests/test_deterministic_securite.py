"""Tests de securite du chemin deterministe (C2-2).

Chaque execution doit passer par le garde-fou central. Les refus ne
doivent produire aucun effet de bord.
"""
import os
import tempfile
import unittest

from core.agent_permissions import obtenir_outils_autorises
from core.deterministic_actions import OUTILS_DETERMINISTES, tenter


class TestDeterministicSecurite(unittest.TestCase):
    def setUp(self):
        # Le repertoire courant est le sandbox pytest (isolation automatique).
        self.temp = tempfile.TemporaryDirectory(
            dir=os.path.join(os.getcwd(), "espace_travail")
        )
        self.addCleanup(self.temp.cleanup)

    def chemin(self, nom):
        return os.path.join(self.temp.name, nom)

    def test_outils_deterministes_tous_connus(self):
        from core.tool_guard import outil_connu

        for outil in OUTILS_DETERMINISTES:
            self.assertTrue(outil_connu(outil), outil)

    def test_ecriture_refusee_agent_securite(self):
        cible = self.chemin("refus_securite.txt")
        resultat = tenter(
            f"Ecris le fichier {cible} contenant INTERDIT",
            agent="09_securite_ia",
            outils_autorises=["ecrire_fichier"],
        )

        self.assertFalse(resultat["ok"])
        self.assertTrue(resultat["refuse"])
        self.assertEqual(resultat["code"], "hors_permissions_agent")
        self.assertFalse(os.path.exists(cible))

    def test_ecriture_refusee_sans_liste_explicite(self):
        cible = self.chemin("refus_sans_liste.txt")
        resultat = tenter(
            f"Ecris le fichier {cible} contenant INTERDIT",
            agent="01_developpeur",
        )

        self.assertFalse(resultat["ok"])
        self.assertTrue(resultat["refuse"])
        self.assertFalse(os.path.exists(cible))

    def test_ecriture_refusee_liste_incomplete(self):
        cible = self.chemin("refus_liste_incomplete.txt")
        resultat = tenter(
            f"Ecris le fichier {cible} contenant INTERDIT",
            agent="01_developpeur",
            outils_autorises=["lire_fichier"],
        )

        self.assertFalse(resultat["ok"])
        self.assertTrue(resultat["refuse"])
        self.assertEqual(resultat["statut"], "non_autorise")
        self.assertFalse(os.path.exists(cible))

    def test_ecriture_refusee_agent_inconnu(self):
        cible = self.chemin("refus_agent_inconnu.txt")
        resultat = tenter(
            f"Ecris le fichier {cible} contenant INTERDIT",
            agent="99_agent_inexistant",
            outils_autorises=["ecrire_fichier"],
        )

        self.assertFalse(resultat["ok"])
        self.assertEqual(resultat["statut"], "non_autorise")
        self.assertFalse(os.path.exists(cible))

    def test_ecriture_autorisee_developpeur(self):
        cible = self.chemin("autorise.txt")
        resultat = tenter(
            f"Ecris le fichier {cible} contenant AUTORISE",
            agent="01_developpeur",
            outils_autorises=obtenir_outils_autorises("01_developpeur"),
        )

        self.assertTrue(resultat["ok"])
        self.assertEqual(resultat["outil"], "ecrire_fichier")
        with open(cible, encoding="utf-8") as fichier:
            self.assertEqual(fichier.read(), "AUTORISE")

    def test_suppression_fichier_refusee_securite(self):
        cible = self.chemin("a_conserver.txt")
        with open(cible, "w", encoding="utf-8") as fichier:
            fichier.write("conserver")

        resultat = tenter(
            f"supprime le fichier {cible}",
            agent="09_securite_ia",
            outils_autorises=["supprimer_fichier"],
        )

        self.assertFalse(resultat["ok"])
        self.assertTrue(resultat["refuse"])
        self.assertTrue(os.path.exists(cible))

    def test_suppression_dossier_refusee_securite(self):
        cible = self.chemin("dossier_a_conserver")
        os.makedirs(cible)

        resultat = tenter(
            f"supprime le dossier {cible}",
            agent="09_securite_ia",
            outils_autorises=["supprimer_dossier"],
        )

        self.assertFalse(resultat["ok"])
        self.assertTrue(resultat["refuse"])
        self.assertTrue(os.path.isdir(cible))

    def test_suppression_fichier_autorisee_developpeur(self):
        cible = self.chemin("a_supprimer.txt")
        with open(cible, "w", encoding="utf-8") as fichier:
            fichier.write("supprimer")

        resultat = tenter(
            f"supprime le fichier {cible}",
            agent="01_developpeur",
            outils_autorises=["supprimer_fichier"],
        )

        self.assertTrue(resultat["ok"])
        self.assertEqual(resultat["outil"], "supprimer_fichier")
        self.assertFalse(os.path.exists(cible))

    def test_lecture_autorisee_securite(self):
        cible = self.chemin("lisible.txt")
        with open(cible, "w", encoding="utf-8") as fichier:
            fichier.write("LISIBLE")

        resultat = tenter(
            f"lis le fichier {cible}",
            agent="09_securite_ia",
            outils_autorises=["lire_fichier"],
        )

        self.assertTrue(resultat["ok"])
        self.assertEqual(resultat["outil"], "lire_fichier")
        self.assertIn("LISIBLE", resultat["resultat"])

    def test_outil_telephone_refuse_avant_execution(self):
        resultat = tenter(
            "allume la torche",
            agent="09_securite_ia",
            outils_autorises=["lampe_torche"],
        )

        self.assertFalse(resultat["ok"])
        self.assertTrue(resultat["refuse"])
        self.assertEqual(resultat["outil"], "lampe_torche")
        self.assertEqual(resultat["code"], "hors_permissions_agent")


if __name__ == "__main__":
    unittest.main()
