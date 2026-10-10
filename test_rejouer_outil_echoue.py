import unittest

from core.ai_engine import AIEngine


class TestRejouerOutilEchoue(unittest.TestCase):
    def creer_moteur(self):
        moteur = AIEngine.__new__(AIEngine)
        moteur.derniers_resultats_outils = [{
            "outil": "outil_test",
            "arguments": {"fichier": "exemple.py"},
            "statut": "verification_echec",
            "verification": {"verifie": False},
        }]
        moteur.outils_autorises = ["autorisation_precedente"]
        return moteur

    def test_echec_rejoue_conserve_les_diagnostics(self):
        moteur = self.creer_moteur()

        def simuler_echec(outil, arguments):
            moteur.derniers_resultats_outils.append({
                "outil": outil,
                "arguments": arguments,
                "statut": "verification_echec",
                "verification": {"verifie": False},
            })

        moteur._executer_outil = simuler_echec

        resultat = moteur.rejouer_outil_echoue(
            "outil_test", ["outil_test"]
        )

        self.assertFalse(resultat)
        self.assertEqual(len(moteur.derniers_resultats_outils), 2)
        self.assertEqual(
            moteur.outils_autorises, ["autorisation_precedente"]
        )

    def test_succes_verifie_accepte(self):
        moteur = self.creer_moteur()

        def simuler_succes(outil, arguments):
            moteur.derniers_resultats_outils.append({
                "outil": outil,
                "arguments": arguments,
                "statut": "succes",
                "verification": {"verifie": True},
            })

        moteur._executer_outil = simuler_succes

        resultat = moteur.rejouer_outil_echoue(
            "outil_test", ["outil_test"]
        )

        self.assertTrue(resultat)
        self.assertEqual(len(moteur.derniers_resultats_outils), 1)
        self.assertEqual(
            moteur.derniers_resultats_outils[0]["statut"], "succes"
        )


if __name__ == "__main__":
    unittest.main()
