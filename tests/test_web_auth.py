"""Tests de l'authentification web (C1), sans dependance ni appel reseau."""

import os
import re
import time
import unittest
from unittest.mock import patch

from interface import app as app_module
from interface.app import app

MOT_DE_PASSE = "mot-de-passe-de-test-c1"


def _extraire_csrf(page):
    correspondance = re.search(
        r'name="csrf" value="([^"]+)"',
        page.decode("utf-8"),
    )
    if correspondance is None:
        raise AssertionError("Jeton CSRF absent de la page de connexion.")
    return correspondance.group(1)


class TestWebAuth(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"JARVIS_WEB_PASSWORD": MOT_DE_PASSE})
        self._env.start()
        self.addCleanup(self._env.stop)
        app_module._reinitialiser_limite_connexions()
        self.addCleanup(app_module._reinitialiser_limite_connexions)
        self.client = app.test_client()

    def _page_connexion(self):
        reponse = self.client.get("/login")
        self.assertEqual(reponse.status_code, 200)
        return _extraire_csrf(reponse.data)

    def _connecter(self, mot_de_passe=MOT_DE_PASSE):
        jeton = self._page_connexion()
        return self.client.post(
            "/login",
            data={"mot_de_passe": mot_de_passe, "csrf": jeton},
        )

    def test_acces_refuse_sans_session(self):
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/login", reponse.headers["Location"])

    def test_api_refusee_en_json_sans_session(self):
        reponse = self.client.get("/api/missions")
        self.assertEqual(reponse.status_code, 401)
        self.assertEqual(reponse.get_json()["erreur"], "Authentification requise.")

    def test_health_reste_public(self):
        reponse = self.client.get("/health")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data, b"ok")

    def test_mot_de_passe_incorrect_refuse(self):
        reponse = self._connecter(mot_de_passe="mauvais-mot-de-passe")
        self.assertEqual(reponse.status_code, 401)
        self.assertIn("Mot de passe incorrect", reponse.get_data(as_text=True))

        self.assertEqual(self.client.get("/").status_code, 302)

    def test_connexion_reussie_donne_acces(self):
        reponse = self._connecter()
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse.headers["Location"], "/")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_csrf_absent_refuse_meme_avec_bon_mot_de_passe(self):
        reponse = self.client.post(
            "/login",
            data={"mot_de_passe": MOT_DE_PASSE},
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.client.get("/").status_code, 302)

        # La page renvoyee contient un nouveau jeton : la tentative peut reussir.
        jeton = _extraire_csrf(reponse.data)
        reprise = self.client.post(
            "/login",
            data={"mot_de_passe": MOT_DE_PASSE, "csrf": jeton},
        )
        self.assertEqual(reprise.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_csrf_invalide_refuse(self):
        self._page_connexion()
        reponse = self.client.post(
            "/login",
            data={"mot_de_passe": MOT_DE_PASSE, "csrf": "jeton-invalide"},
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_deconnexion_ferme_la_session(self):
        self._connecter()
        self.assertEqual(self.client.get("/").status_code, 200)

        reponse = self.client.post("/deconnexion")
        self.assertEqual(reponse.status_code, 302)
        self.assertIn("/login", reponse.headers["Location"])
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_redirection_externe_ignoree(self):
        reponse = self.client.get("/login?suivant=//exemple-malveillant.test")
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn(b"exemple-malveillant.test", reponse.data)

        jeton = _extraire_csrf(reponse.data)
        connexion = self.client.post(
            "/login",
            data={
                "mot_de_passe": MOT_DE_PASSE,
                "csrf": jeton,
                "suivant": "//exemple-malveillant.test",
            },
        )
        self.assertEqual(connexion.status_code, 302)
        self.assertEqual(connexion.headers["Location"], "/")

    def test_changement_de_mot_de_passe_invalide_les_sessions(self):
        self._connecter()
        self.assertEqual(self.client.get("/").status_code, 200)

        with patch.dict(os.environ, {"JARVIS_WEB_PASSWORD": "nouveau-mot-de-passe"}):
            self.assertEqual(self.client.get("/").status_code, 302)

    def test_tentatives_limitees_puis_blocage(self):
        for _ in range(4):
            self.assertEqual(self._connecter("mauvais").status_code, 401)

        bloque = self._connecter("mauvais")
        self.assertEqual(bloque.status_code, 429)
        self.assertIn("Trop de tentatives", bloque.get_data(as_text=True))
        self.assertGreaterEqual(int(bloque.headers["Retry-After"]), 1)

        # Meme le bon mot de passe est refuse pendant le blocage.
        self.assertEqual(self._connecter().status_code, 429)

    def test_connexion_reussie_reinitialise_le_compteur(self):
        for _ in range(3):
            self.assertEqual(self._connecter("mauvais").status_code, 401)
        self.assertEqual(self._connecter().status_code, 302)

        for _ in range(4):
            self.assertEqual(self._connecter("mauvais").status_code, 401)
        self.assertEqual(self._connecter("mauvais").status_code, 429)

    def test_blocage_expire(self):
        for _ in range(5):
            self._connecter("mauvais")
        self.assertEqual(self._connecter("mauvais").status_code, 429)

        with app_module._limite_verrou:
            app_module._limite_connexions["127.0.0.1"]["bloque_jusqua"] = (
                time.monotonic() - 1
            )

        self.assertEqual(self._connecter().status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_seuil_de_tentatives_configurable(self):
        with patch.dict(os.environ, {"JARVIS_LOGIN_MAX_TENTATIVES": "2"}):
            self.assertEqual(self._connecter("mauvais").status_code, 401)
            self.assertEqual(self._connecter("mauvais").status_code, 429)

    def test_authentification_desactivee_sans_mot_de_passe(self):
        with patch.dict(os.environ, {"JARVIS_WEB_PASSWORD": ""}):
            self.assertEqual(self.client.get("/").status_code, 200)
            reponse = self.client.get("/login")
            self.assertEqual(reponse.status_code, 302)
            self.assertEqual(reponse.headers["Location"], "/")


if __name__ == "__main__":
    unittest.main()
