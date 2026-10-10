import unittest

from core.validation_manager import ValidationManager


class FauxLogger:
    def enregistrer(self, *args, **kwargs):
        pass


def diagnostic(outil, type_echec="verification"):
    return {"echec": True, "type": type_echec, "outil": outil}


def resultats(outil):
    return [{"outil": outil, "statut": "verification_echec"}]


class TestPolitiqueCorrection(unittest.TestCase):
    def setUp(self):
        self.vm = ValidationManager(FauxLogger())

    def autoriser(self, diag, res=None):
        return self.vm.autoriser_correction(diag, resultats_outils=res)

    def test_outils_interdits_refuses(self):
        for outil in ("supprimer_fichier", "supprimer_tache",
                      "supprimer_projet", "github_ecrire_fichier",
                      "memoriser_info"):
            vm = ValidationManager(FauxLogger())
            r = vm.autoriser_correction(diagnostic(outil),
                                        resultats_outils=resultats(outil))
            self.assertFalse(r["autorisee"], outil)
            self.assertIn("interdite", r["raison"], outil)

    def test_outils_sans_politique_refuses(self):
        for outil in ("creer_dossier", "github_creer_repo", "outil_inconnu"):
            vm = ValidationManager(FauxLogger())
            r = vm.autoriser_correction(diagnostic(outil),
                                        resultats_outils=resultats(outil))
            self.assertFalse(r["autorisee"], outil)

    def test_ecrire_fichier_autorise_une_seule_fois(self):
        diag = diagnostic("ecrire_fichier")
        res = resultats("ecrire_fichier")
        self.assertTrue(self.autoriser(diag, res)["autorisee"])
        self.assertFalse(self.autoriser(diag, res)["autorisee"])

    def test_remise_a_zero_permet_une_nouvelle_correction(self):
        diag = diagnostic("ecrire_fichier")
        res = resultats("ecrire_fichier")
        self.autoriser(diag, res)
        self.vm.corrections_utilisees = 0
        self.assertTrue(self.autoriser(diag, res)["autorisee"])

    def test_type_echec_autre_que_verification_refuse(self):
        r = self.autoriser(diagnostic("ecrire_fichier", "reponse"),
                           resultats("ecrire_fichier"))
        self.assertFalse(r["autorisee"])

    def test_sans_resultat_enregistre_refuse(self):
        r = self.autoriser(diagnostic("ecrire_fichier"), [])
        self.assertFalse(r["autorisee"])

    def test_diagnostics_invalides_refuses(self):
        self.assertFalse(self.autoriser(None)["autorisee"])
        self.assertFalse(self.autoriser({"echec": False})["autorisee"])
        self.assertFalse(self.autoriser({"echec": True})["autorisee"])


if __name__ == "__main__":
    unittest.main()
