import unittest
from unittest.mock import Mock

from core.ai_engine import AIEngine


class TestAIEngineOrigine(unittest.TestCase):

    def creer_moteur(self):
        moteur = AIEngine.__new__(AIEngine)
        moteur.router = Mock()
        moteur.router.demander.side_effect = (
            lambda *args: moteur._message_utilisateur_courant
        )
        moteur.outils_autorises = ["ancien_outil"]
        moteur.mode_action = True
        moteur._message_utilisateur_courant = "ancien message"
        return moteur

    def test_conserve_la_demande_originale(self):
        moteur = self.creer_moteur()

        resultat = moteur.demander(
            "Objectif de la sous-tache",
            outils_autorises=["lire_fichier"],
            mode_action=True,
            message_utilisateur_origine="Demande originale de suppression",
        )

        self.assertEqual(resultat, "Demande originale de suppression")
        self.assertEqual(moteur._message_utilisateur_courant, "ancien message")
        self.assertEqual(moteur.outils_autorises, ["ancien_outil"])
        self.assertTrue(moteur.mode_action)

    def test_ancien_appel_utilise_le_message_fourni(self):
        moteur = self.creer_moteur()

        resultat = moteur.demander(
            "Demande classique",
            outils_autorises=[],
            mode_action=False,
        )

        self.assertEqual(resultat, "Demande classique")
        self.assertEqual(moteur._message_utilisateur_courant, "ancien message")


if __name__ == "__main__":
    unittest.main()
