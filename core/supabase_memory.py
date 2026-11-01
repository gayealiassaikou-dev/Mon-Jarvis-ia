"""Connexion sécurisée à Supabase pour la mémoire persistante de Sam Sarr."""

import getpass
import json
import os
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


RACINE = Path(__file__).resolve().parent.parent
FICHIER_SESSION = RACINE / ".supabase_session.json"
TIMEOUT = 20


class SupabaseMemoryError(Exception):
    """Erreur de connexion ou de session Supabase."""


class SupabaseMemory:
    def __init__(self):
        load_dotenv(RACINE / ".env")

        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.cle_publique = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")

        if not self.url or not self.cle_publique:
            raise SupabaseMemoryError(
                "Configuration Supabase absente dans le fichier .env."
            )

        self.session = None

    def _enregistrer_session(self, donnees):
        contenu = {
            "access_token": donnees["access_token"],
            "refresh_token": donnees["refresh_token"],
            "user_id": donnees["user"]["id"],
            "expires_at": int(time.time()) + int(donnees.get("expires_in", 3600)),
        }

        fd, chemin_temp = tempfile.mkstemp(
            prefix=".supabase_session_",
            suffix=".tmp",
            dir=RACINE,
        )

        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fichier:
                json.dump(contenu, fichier)
                fichier.flush()
                os.fsync(fichier.fileno())

            os.replace(chemin_temp, FICHIER_SESSION)
            os.chmod(FICHIER_SESSION, 0o600)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(chemin_temp):
                os.unlink(chemin_temp)
            raise

        self.session = contenu

    def _charger_session(self):
        if not FICHIER_SESSION.exists():
            return False

        try:
            os.chmod(FICHIER_SESSION, 0o600)
            with FICHIER_SESSION.open("r", encoding="utf-8") as fichier:
                self.session = json.load(fichier)

            return bool(
                self.session.get("access_token")
                and self.session.get("refresh_token")
                and self.session.get("user_id")
            )
        except (OSError, ValueError, TypeError):
            self.session = None
            return False

    def connecter(self):
        email = input("Adresse e-mail du compte Sam Sarr : ").strip()
        mot_de_passe = getpass.getpass("Mot de passe Supabase : ")

        if not email or not mot_de_passe:
            raise SupabaseMemoryError("Identifiants incomplets.")

        try:
            reponse = requests.post(
                f"{self.url}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": self.cle_publique,
                    "Content-Type": "application/json",
                },
                json={"email": email, "password": mot_de_passe},
                timeout=TIMEOUT,
            )
        except requests.RequestException as erreur:
            raise SupabaseMemoryError(
                "Connexion réseau à Supabase impossible."
            ) from erreur
        finally:
            mot_de_passe = None

        if not reponse.ok:
            try:
                erreur = reponse.json()
                detail = (
                    erreur.get("msg")
                    or erreur.get("error_description")
                    or erreur.get("message")
                    or erreur.get("error")
                    or "Motif non précisé"
                )
            except ValueError:
                detail = "Réponse non JSON"
            raise SupabaseMemoryError(
                f"Authentification refusée (HTTP {reponse.status_code}) : {detail}"
            )

        try:
            donnees = reponse.json()
            self._enregistrer_session(donnees)
        except (ValueError, KeyError, TypeError) as erreur:
            raise SupabaseMemoryError(
                "Réponse d'authentification Supabase invalide."
            ) from erreur

        return self.session["user_id"]

    def _rafraichir_session(self):
        if not self.session or not self.session.get("refresh_token"):
            raise SupabaseMemoryError("Aucune session à renouveler.")

        try:
            reponse = requests.post(
                f"{self.url}/auth/v1/token?grant_type=refresh_token",
                headers={
                    "apikey": self.cle_publique,
                    "Content-Type": "application/json",
                },
                json={"refresh_token": self.session["refresh_token"]},
                timeout=TIMEOUT,
            )
        except requests.RequestException as erreur:
            raise SupabaseMemoryError(
                "Impossible de renouveler la session Supabase."
            ) from erreur

        if not reponse.ok:
            raise SupabaseMemoryError(
                f"Renouvellement refusé (HTTP {reponse.status_code})."
            )

        try:
            self._enregistrer_session(reponse.json())
        except (ValueError, KeyError, TypeError) as erreur:
            raise SupabaseMemoryError(
                "Réponse de renouvellement invalide."
            ) from erreur

    def obtenir_access_token(self):
        if self.session is None and not self._charger_session():
            raise SupabaseMemoryError("Aucune session enregistrée.")

        if int(self.session.get("expires_at", 0)) <= int(time.time()) + 60:
            self._rafraichir_session()

        return self.session["access_token"]

    def verifier_connexion(self):
        token = self.obtenir_access_token()

        try:
            reponse = requests.get(
                f"{self.url}/auth/v1/user",
                headers={
                    "apikey": self.cle_publique,
                    "Authorization": f"Bearer {token}",
                },
                timeout=TIMEOUT,
            )
        except requests.RequestException as erreur:
            raise SupabaseMemoryError(
                "Vérification de la session impossible."
            ) from erreur

        if not reponse.ok:
            raise SupabaseMemoryError(
                f"Session non valide (HTTP {reponse.status_code})."
            )

        return True
