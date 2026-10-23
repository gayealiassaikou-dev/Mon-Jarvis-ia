import unittest
from unittest.mock import Mock

from core.jarvis import Jarvis


class TestJarvisLocalFirst(unittest.TestCase):
    def setUp(self):
        self.jarvis = object.__new__(Jarvis)
        self.jarvis.validation_manager = Mock()
        self.jarvis.validation_manager.corrections_utilisees = 0
        self.jarvis.logger = Mock()
        self.jarvis.command_manager = Mock()
        self.jarvis.command_manager.traiter.return_value = (
            "Commande inconnue. Tape aide pour voir les commandes."
        )
        self.jarvis.local_brain = Mock()
        self.jarvis.local_brain.repondre.return_value = (
            "Voici la réponse locale."
        )
        self.jarvis.memory_manager = Mock()
        self.jarvis.decision_engine = Mock()

    def test_reponse_locale_ne_declenche_pas_le_moteur_ia(self):
        reponse = self.jarvis.traiter_commande(
            "Question traitée localement",
            retourner_reponse=True,
        )

        self.assertEqual(reponse, "Voici la réponse locale.")
        self.jarvis.decision_engine.decider.assert_not_called()
        self.jarvis.memory_manager.ajouter_echange.assert_called_once_with(
            "Question traitée localement",
            "Voici la réponse locale.",
        )
        self.jarvis.logger.enregistrer.assert_any_call(
            "[LOCAL] Réponse fournie sans fournisseur IA."
        )

    def test_question_non_resolue_localement_passe_au_directeur_ia(self):
        self.jarvis.local_brain.repondre.return_value = None
        self.jarvis.decision_engine.decider.side_effect = RuntimeError(
            "Arrêt volontaire du test après l'appel au directeur IA."
        )

        with self.assertRaisesRegex(
            RuntimeError, "Arrêt volontaire du test"
        ):
            self.jarvis.traiter_commande(
                "Question complexe non résolue localement",
                retourner_reponse=True,
            )

        self.jarvis.local_brain.repondre.assert_called_once_with(
            "Question complexe non résolue localement"
        )
        self.jarvis.decision_engine.decider.assert_called_once_with(
            "Question complexe non résolue localement"
        )
        self.jarvis.memory_manager.ajouter_echange.assert_not_called()


if __name__ == "__main__":
    unittest.main()
