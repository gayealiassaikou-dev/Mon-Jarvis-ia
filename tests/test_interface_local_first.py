import unittest
from unittest.mock import patch

from interface.app import app


class TestInterfaceLocalFirst(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("interface.app.jarvis.traiter_commande")
    def test_envoyer_affiche_la_reponse_locale_sans_appel_ia(self, traiter):
        traiter.return_value = "Réponse locale de Sam Sarr."

        reponse = self.client.post(
            "/envoyer",
            data={"message": "Quelle est ma demande ?"},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertIn(b"Quelle est ma demande ?", reponse.data)
        self.assertIn(b"R\xc3\xa9ponse locale de Sam Sarr.", reponse.data)
        traiter.assert_called_once_with(
            "Quelle est ma demande ?",
            retourner_reponse=True,
        )


if __name__ == "__main__":
    unittest.main()
