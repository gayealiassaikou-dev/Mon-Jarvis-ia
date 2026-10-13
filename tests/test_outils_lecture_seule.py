import unittest

from core.ai_engine import FONCTIONS_DISPONIBLES, OUTILS_LECTURE_SEULE

ECRITURE = {
    "ecrire_fichier", "supprimer_fichier", "creer_dossier",
    "github_creer_repo", "github_ecrire_fichier", "creer_projet",
    "ajouter_tache", "terminer_tache", "supprimer_tache",
    "supprimer_projet", "modifier_statut_projet", "memoriser_info",
}


class TestOutilsLectureSeule(unittest.TestCase):
    def test_aucun_outil_d_ecriture_dans_la_liste(self):
        self.assertEqual(OUTILS_LECTURE_SEULE & ECRITURE, set())

    def test_les_outils_de_lecture_existent(self):
        for nom in OUTILS_LECTURE_SEULE - {"rechercher_souvenir"}:
            with self.subTest(outil=nom):
                self.assertIn(nom, FONCTIONS_DISPONIBLES)


if __name__ == "__main__":
    unittest.main()
