import unittest
from unittest.mock import patch, MagicMock
import core.ai_engine as moteur
import requests
import time

class TestGroqDeuxCles(unittest.TestCase):
    def setUp(self):
        # Initialise l'instance du moteur d'IA avec deux fausses clés
        self.moteur = moteur.AIEngine()
        self.moteur.api_key = "FAUSSE_CLE_PRINCIPALE"
        self.moteur.api_key_1 = "FAUSSE_CLE_SECONDAIRE"
        self.moteur.action_engagee = False

    def _patch_appeler(self, side_effect=None, return_value=None):
        """Helper pour patcher _appeler_openai_compatible et capturer les en‑têtes."""
        patcher = patch.object(self.moteur, "_appeler_openai_compatible")
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        if side_effect is not None:
            mock.side_effect = side_effect
        if return_value is not None:
            mock.return_value = return_value
        return mock

    def test_principale_ok(self):
        """Un seul appel avec la clé principale qui réussit."""
        mock = self._patch_appeler(return_value="résultat")
        resultat = self.moteur._demander_groq("bonjour")
        self.assertEqual(resultat, "résultat")
        mock.assert_called_once()
        args, kwargs = mock.call_args
        # le deuxième argument positionnel doit contenir le header Authorization avec la clé principale
        self.assertIn(self.moteur.api_key, args[1].get("Authorization", ""))

    def test_principale_echec_seconde_ok(self):
        """La première clé échoue, la seconde réussit."""
        def side_effect(*args, **kwargs):
            # première tentative lève une exception, deuxième retourne un résultat
            if side_effect.called:
                return "résultat_secondaire"
            side_effect.called = True
            raise Exception("Erreur clé principale")
        side_effect.called = False

        mock = self._patch_appeler(side_effect=side_effect)
        resultat = self.moteur._demander_groq("bonjour")
        self.assertEqual(resultat, "résultat_secondaire")
        self.assertEqual(mock.call_count, 2)
        # première appel avec la clé principale
        first_call_args = mock.call_args_list[0][0]
        self.assertIn(self.moteur.api_key, first_call_args[1].get("Authorization", ""))
        # deuxième appel avec la clé secondaire
        second_call_args = mock.call_args_list[1][0]
        self.assertIn(self.moteur.api_key_1, second_call_args[1].get("Authorization", ""))

    def test_deux_cles_en_echec(self):
        """Les deux clés échouent, une exception est levée après deux tentatives."""
        mock = self._patch_appeler(side_effect=Exception("Clé invalide"))
        with self.assertRaises(Exception) as cm:
            self.moteur._demander_groq("bonjour")
        self.assertEqual(mock.call_count, 2)
        self.assertIn("Clé invalide", str(cm.exception))

    def test_action_engagee_true_premier_appel_echec(self):
        """Si action_engagee devient True pendant le premier appel, aucune seconde tentative n'est faite."""
        def side_effect(*args, **kwargs):
            # Simuler que l'action_engagee passe à True pendant l'appel
            self.moteur.action_engagee = True
            raise Exception("Erreur première clé")
        mock = self._patch_appeler(side_effect=side_effect)
        with self.assertRaises(Exception):
            self.moteur._demander_groq("bonjour")
        # Une seule tentative car action_engagee est maintenant True
        self.assertEqual(mock.call_count, 1)

    def test_cle_secondaire_absente_ou_identique(self):
        """Si la clé secondaire est absente ou identique à la principale, un seul appel est effectué."""
        # Cas 1 : clé secondaire absente
        self.moteur.api_key_1 = None
        mock = self._patch_appeler(return_value="résultat")
        self.moteur._demander_groq("bonjour")
        self.assertEqual(mock.call_count, 1)

        # Cas 2 : clé secondaire identique à la principale
        self.moteur.api_key_1 = self.moteur.api_key
        mock2 = self._patch_appeler(return_value="résultat")
        self.moteur._demander_groq("bonjour")
        self.assertEqual(mock2.call_count, 1)

    def test_quota_429_reessai(self):
        """Vérifie que le mécanisme de ré‑essai sur 429 effectue au maximum 3 appels."""
        # Patch requests.post pour renvoyer une réponse 429 avec header Retry-After = 0
        response_429 = MagicMock()
        response_429.status_code = 429
        response_429.headers = {"retry-after": "0"}
        response_ok = MagicMock()
        response_ok.status_code = 200
        response_ok.json.return_value = {"result": "ok"}

        post_mock = patch('core.ai_engine.requests.post', side_effect=[response_429, response_429, response_ok]).start()
        self.addCleanup(patch.stopall)

        # Patch time.sleep pour éviter les délais réels
        sleep_mock = patch('time.sleep', return_value=None).start()
        self.addCleanup(patch.stopall)

        # Appel de la méthode interne qui utilise _post_avec_reessai_429
        resultat = self.moteur._post_avec_reessai_429("http://x", {}, {}, 5)
        self.assertEqual(resultat.status_code, 200)
        self.assertEqual(post_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_count, 2)  # deux pauses entre les trois appels

    def test_pas_de_fuite_de_cle_dans_exception(self):
        """S’assure que les messages d’erreur ne contiennent pas les clés API."""
        # Simuler une réponse HTTP 401
        response_401 = MagicMock()
        response_401.status_code = 401
        response_401.text = "Unauthorized"
        post_mock = patch('core.ai_engine.requests.post', return_value=response_401).start()
        self.addCleanup(patch.stopall)

        with self.assertRaises(Exception) as cm:
            self.moteur._demander_groq("bonjour")
        message = str(cm.exception)
        # Aucun des deux faux tokens ne doit apparaître dans le message
        self.assertNotIn(self.moteur.api_key, message)
        self.assertNotIn(self.moteur.api_key_1 or "", message)
        # Vérifier également la représentation de l'exception
        self.assertNotIn(self.moteur.api_key, repr(cm.exception))
        self.assertNotIn(self.moteur.api_key_1 or "", repr(cm.exception))

if __name__ == "__main__":
    unittest.main()
