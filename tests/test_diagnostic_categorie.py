import unittest

from core.validation_manager import ValidationManager, classer_erreur


class FauxLogger:
    def enregistrer(self, *args, **kwargs):
        pass


class TestClasserErreur(unittest.TestCase):
    def test_messages_reels_de_tools(self):
        cas = [
            ("Erreur : accès refusé en dehors du projet.", "acces_refuse"),
            ("Erreur : x.py est un fichier protege, modification refusee.",
             "acces_refuse"),
            ("Erreur : le fichier x.py n'existe pas.", "introuvable"),
            ("Erreur : le projet 'p' existe deja.", "deja_existant"),
            ("Erreur : x est un dossier, pas un fichier.",
             "argument_invalide"),
            ("Erreur : nom de depot invalide.", "argument_invalide"),
            ("Erreur : vérification échouée après écriture de x.",
             "verification_echouee"),
            ("Erreur : cle API Tavily manquante (verifie le fichier .env).",
             "authentification"),
            ("Erreur : token GitHub invalide ou expire.",
             "authentification"),
            ("Erreur : la recherche web a expire (timeout).",
             "service_externe"),
            ("Erreur : limite de requetes Tavily atteinte.",
             "service_externe"),
            ("Erreur : acces refuse ou limite de requetes GitHub atteinte.",
             "acces_refuse"),
            ("Erreur : quelque chose d'imprevu.", "inconnue"),
            (None, "inconnue"),
        ]
        for message, attendu in cas:
            with self.subTest(message=message):
                self.assertEqual(classer_erreur(message), attendu)


class TestDiagnosticCategorie(unittest.TestCase):
    def setUp(self):
        self.vm = ValidationManager(FauxLogger())
        self.validation = {"valide": False, "avertissement": "echec"}

    def test_pas_d_echec_categorie_none(self):
        d = self.vm.diagnostiquer_echec({"valide": True}, [])
        self.assertFalse(d["echec"])
        self.assertIsNone(d["categorie"])

    def test_echec_action_ecrire_fichier_corrigeable(self):
        resultats = [{
            "outil": "ecrire_fichier",
            "statut": "echec_execution",
            "execute": False,
            "resultat": "Erreur : le dossier parent de a/b.txt n'existe pas.",
        }]
        d = self.vm.diagnostiquer_echec(self.validation, resultats)
        self.assertEqual(d["type"], "action")
        self.assertEqual(d["categorie"], "introuvable")
        self.assertTrue(d["corrigeable"])

    def test_echec_action_autre_outil_non_corrigeable(self):
        resultats = [{
            "outil": "lire_fichier",
            "statut": "echec_execution",
            "execute": False,
            "resultat": "Erreur : le fichier a.txt n'existe pas.",
        }]
        d = self.vm.diagnostiquer_echec(self.validation, resultats)
        self.assertEqual(d["categorie"], "introuvable")
        self.assertFalse(d["corrigeable"])

    def test_echec_verification(self):
        resultats = [{
            "outil": "ecrire_fichier",
            "statut": "succes",
            "execute": True,
            "resultat": "ok",
            "verification": {
                "verifie": False,
                "details": "Erreur : vérification échouée après écriture.",
            },
        }]
        d = self.vm.diagnostiquer_echec(self.validation, resultats)
        self.assertEqual(d["type"], "verification")
        self.assertEqual(d["categorie"], "verification_echouee")
        self.assertTrue(d["corrigeable"])

    def test_echec_reponse_sans_outil(self):
        d = self.vm.diagnostiquer_echec(
            {"valide": False, "avertissement": "Reponse vide"}, []
        )
        self.assertEqual(d["type"], "reponse")
        self.assertEqual(d["categorie"], "inconnue")
        self.assertFalse(d["corrigeable"])
        self.assertIsNone(d["outil"])



class TestAutorisationCorrection(unittest.TestCase):
    def setUp(self):
        self.vm = ValidationManager(FauxLogger())

    def diagnostic(self, categorie="introuvable", type_echec="action"):
        return {
            "echec": True,
            "outil": "ecrire_fichier",
            "type": type_echec,
            "categorie": categorie,
            "corrigeable": True,
        }

    def test_autorise_dossier_parent_manquant(self):
        diagnostic = self.diagnostic()
        resultats = [{
            "outil": "ecrire_fichier",
            "statut": "echec_execution",
            "resultat": "Erreur : le dossier parent de a/b.txt n'existe pas.",
        }]
        decision = self.vm.autoriser_correction(diagnostic, resultats)
        self.assertTrue(decision["autorisee"])

    def test_refuse_fichier_introuvable_sans_parent_manquant(self):
        diagnostic = self.diagnostic()
        resultats = [{
            "outil": "ecrire_fichier",
            "statut": "echec_execution",
            "resultat": "Erreur : le fichier a.txt n'existe pas.",
        }]
        decision = self.vm.autoriser_correction(diagnostic, resultats)
        self.assertFalse(decision["autorisee"])

    def test_conserve_correction_echec_verification(self):
        diagnostic = self.diagnostic(
            categorie="verification_echouee",
            type_echec="verification",
        )
        resultats = [{
            "outil": "ecrire_fichier",
            "statut": "succes",
            "resultat": "ok",
            "verification": {
                "verifie": False,
                "details": "Erreur : vérification échouée après écriture.",
            },
        }]
        decision = self.vm.autoriser_correction(diagnostic, resultats)
        self.assertTrue(decision["autorisee"])

    def test_refuse_deuxieme_correction(self):
        diagnostic = self.diagnostic(
            categorie="verification_echouee",
            type_echec="verification",
        )
        resultats = [{
            "outil": "ecrire_fichier",
            "statut": "succes",
            "resultat": "ok",
            "verification": {"verifie": False, "details": "Échec"},
        }]
        premiere = self.vm.autoriser_correction(diagnostic, resultats)
        deuxieme = self.vm.autoriser_correction(diagnostic, resultats)
        self.assertTrue(premiere["autorisee"])
        self.assertFalse(deuxieme["autorisee"])

if __name__ == "__main__":
    unittest.main()
