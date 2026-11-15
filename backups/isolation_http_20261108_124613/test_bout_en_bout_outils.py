import json
import os
import tempfile
import unittest
from unittest.mock import patch

import core.ai_engine as moteur
from core.validation_manager import ValidationManager


class FauxLogger:
    def enregistrer(self, *args, **kwargs):
        pass


class FausseReponse:
    def __init__(self, donnees):
        self._donnees = donnees

    def raise_for_status(self):
        pass

    def json(self):
        return self._donnees


def message_outil(chemin, nom="creer_dossier"):
    return {"choices": [{"message": {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {
                "name": nom,
                "arguments": json.dumps({"chemin": chemin}),
            },
        }],
    }}]}


def message_texte(texte):
    return {"choices": [{"message": {"role": "assistant", "content": texte}}]}


class TestBoutEnBoutOutils(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.chemin = os.path.join(tmp.name, "dossier_test")
        self.moteur = moteur.AIEngine()
        self.vm = ValidationManager(FauxLogger())
        self.appels = []

    def outil_qui_cree(self, chemin):
        self.appels.append(chemin)
        os.makedirs(chemin)
        return "Dossier cree : " + chemin

    def outil_qui_ment(self, chemin):
        self.appels.append(chemin)
        return "Dossier cree : " + chemin

    def lancer(self, reponses, outils_autorises, faux_outil):
        suite = iter(reponses)

        def faux_post(*args, **kwargs):
            return FausseReponse(next(suite))

        self.moteur.derniers_resultats_outils = []
        self.moteur.action_engagee = False
        self.moteur.outils_autorises = outils_autorises

        with patch.object(moteur.requests, "post", faux_post), \
                patch.dict(moteur.FONCTIONS_DISPONIBLES,
                           {"creer_dossier": faux_outil}):
            return self.moteur._appeler_openai_compatible(
                "http://faux",
                {},
                "faux-modele",
                "cree un dossier",
                outils=self.moteur._obtenir_outils_autorises(),
                mode_action=True,
            )

    def test_succes_prouve(self):
        reponse = self.lancer(
            [message_outil(self.chemin), message_texte("Le dossier a ete cree.")],
            ["creer_dossier"],
            self.outil_qui_cree,
        )
        resultats = self.moteur.derniers_resultats_outils
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0].get("statut"), "succes")
        self.assertTrue(resultats[0]["verification"]["verifie"])
        self.assertTrue(os.path.isdir(self.chemin))
        validation = self.vm.valider(reponse, "m1", resultats, outils_attendus=True)
        self.assertTrue(validation["valide"])

    def test_fausse_reussite_sans_outil(self):
        reponse = self.lancer(
            [message_texte("C est fait, le dossier est cree.")],
            ["creer_dossier"],
            self.outil_qui_cree,
        )
        self.assertEqual(self.moteur.derniers_resultats_outils, [])
        self.assertEqual(self.appels, [])
        validation = self.vm.valider(reponse, "m1", [], outils_attendus=True)
        self.assertFalse(validation["valide"])

    def test_outil_non_autorise(self):
        reponse = self.lancer(
            [message_outil(self.chemin), message_texte("Termine.")],
            ["lister_fichiers"],
            self.outil_qui_cree,
        )
        resultats = self.moteur.derniers_resultats_outils
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0].get("statut"), "non_autorise")
        self.assertEqual(self.appels, [])
        self.assertFalse(os.path.exists(self.chemin))
        validation = self.vm.valider(reponse, "m1", resultats, outils_attendus=True)
        self.assertFalse(validation["valide"])

    def test_outil_qui_ment_detecte(self):
        reponse = self.lancer(
            [message_outil(self.chemin), message_texte("Le dossier a ete cree.")],
            ["creer_dossier"],
            self.outil_qui_ment,
        )
        resultats = self.moteur.derniers_resultats_outils
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0].get("statut"), "verification_echec")
        self.assertFalse(os.path.exists(self.chemin))
        validation = self.vm.valider(reponse, "m1", resultats, outils_attendus=True)
        self.assertFalse(validation["valide"])


if __name__ == "__main__":
    unittest.main()
