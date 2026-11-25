"""Tests C3 - protection des secrets et donnees personnelles.

Verifie que les outils fichiers refusent les dossiers sensibles
(memory/, data/, backups/, .patches/, interface/data/), les secrets
(.env*, .supabase_session*, config/ai_providers.json*) et les
contournements par traversee de repertoire ou lien symbolique.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from core import tools_fichiers
from core.ai_engine import AIEngine
from core.tools_pdf import lire_pdf

MARQUEUR = "DONNEE_PRIVEE_NE_DOIT_PAS_SORTIR"

CHEMINS_SENSIBLES = (
    ".env",
    ".env.bak_20260101",
    ".env.sauvegarde_supabase",
    ".supabase_session.json",
    ".supabase_session_v5rtukcg.tmp",
    "memory/memory.json",
    "data/missions.json",
    "backups/ancien_env.txt",
    ".patches/patch/core/secret.py",
    "interface/data/conversations.db",
    "config/ai_providers.json",
)


class TestProtectionSecretsC3(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = self.temp.name
        self.addCleanup(self.temp.cleanup)

        self.patch_racine = patch.object(
            tools_fichiers, "DOSSIER_AUTORISE", self.racine
        )
        self.patch_racine.start()
        self.addCleanup(self.patch_racine.stop)

        for chemin in CHEMINS_SENSIBLES:
            self.ecrire(chemin, MARQUEUR)
        self.ecrire(".env.example", "JARVIS_WEB_PASSWORD=\n")
        self.ecrire("projet/lisible.txt", "CONTENU_PUBLIC")

    def ecrire(self, chemin, contenu):
        complet = os.path.join(self.racine, chemin)
        os.makedirs(os.path.dirname(complet), exist_ok=True)
        with open(complet, "w", encoding="utf-8") as fichier:
            fichier.write(contenu)
        return complet

    def lire_direct(self, chemin):
        with open(os.path.join(self.racine, chemin), encoding="utf-8") as fichier:
            return fichier.read()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def test_lecture_des_chemins_sensibles_refusee(self):
        for chemin in CHEMINS_SENSIBLES:
            with self.subTest(chemin=chemin):
                resultat = tools_fichiers.lire_fichier(chemin)
                self.assertTrue(resultat.startswith("Erreur"), resultat)
                self.assertNotIn(MARQUEUR, resultat)

    def test_lecture_pdf_sensible_refusee(self):
        self.ecrire("memory/note.pdf", MARQUEUR)
        resultat = lire_pdf("memory/note.pdf")
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    def test_lister_dossier_sensible_refuse(self):
        for dossier in ("memory", "data", "backups", ".patches",
                        "interface/data"):
            with self.subTest(dossier=dossier):
                resultat = tools_fichiers.lister_fichiers_original_en_ligne(dossier)
                self.assertTrue(resultat.startswith("Erreur"), resultat)

    def test_listing_config_ne_revele_pas_ai_providers(self):
        resultat = tools_fichiers.lister_fichiers_original_en_ligne("config")
        self.assertNotIn("ai_providers.json", resultat)

    def test_lister_racine_masque_les_elements_sensibles(self):
        resultat = tools_fichiers.lister_fichiers_original_en_ligne(".")
        elements = set(resultat.splitlines())
        for nom in ("memory", "data", "backups", ".patches",
                    ".env", ".supabase_session.json"):
            self.assertNotIn(nom, elements)

    def test_modele_env_reste_lisible(self):
        resultat = tools_fichiers.lire_fichier(".env.example")
        self.assertIn("JARVIS_WEB_PASSWORD", resultat)

    # ------------------------------------------------------------------
    # Chemins absolus, relatifs, traversee et liens symboliques
    # ------------------------------------------------------------------
    def test_chemin_absolu_exterieur_refuse(self):
        exterieur = tempfile.TemporaryDirectory()
        self.addCleanup(exterieur.cleanup)
        cible = os.path.join(exterieur.name, "secret.txt")
        with open(cible, "w", encoding="utf-8") as fichier:
            fichier.write(MARQUEUR)

        resultat = tools_fichiers.lire_fichier(cible)
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    def test_chemin_absolu_interne_vers_secret_refuse(self):
        cible = os.path.join(self.racine, "memory", "memory.json")
        resultat = tools_fichiers.lire_fichier(cible)
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    def test_traversee_interne_vers_secret_refusee(self):
        resultat = tools_fichiers.lire_fichier("projet/../memory/memory.json")
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    def test_traversee_relative_refusee(self):
        exterieur = tempfile.TemporaryDirectory()
        self.addCleanup(exterieur.cleanup)
        cible = os.path.join(exterieur.name, "secret.txt")
        with open(cible, "w", encoding="utf-8") as fichier:
            fichier.write(MARQUEUR)

        relatif = os.path.relpath(cible, self.racine)
        self.assertTrue(relatif.startswith(".."))

        resultat = tools_fichiers.lire_fichier(relatif)
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    def test_lien_symbolique_vers_fichier_sensible_refuse(self):
        lien = os.path.join(self.racine, "lien_memoire")
        try:
            os.symlink(
                os.path.join(self.racine, "memory", "memory.json"), lien
            )
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques indisponibles")

        resultat = tools_fichiers.lire_fichier("lien_memoire")
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    def test_lien_symbolique_vers_dossier_sensible_refuse(self):
        lien = os.path.join(self.racine, "lien_dossier")
        try:
            os.symlink(os.path.join(self.racine, "memory"), lien)
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques indisponibles")

        resultat = tools_fichiers.lister_fichiers_original_en_ligne("lien_dossier")
        self.assertTrue(resultat.startswith("Erreur"))

        resultat = tools_fichiers.lire_fichier("lien_dossier/memory.json")
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertNotIn(MARQUEUR, resultat)

    # ------------------------------------------------------------------
    # Ecriture, creation et suppression
    # ------------------------------------------------------------------
    def test_ecriture_dans_dossier_sensible_refusee(self):
        for chemin in ("memory/memory.json", "data/missions.json",
                       ".env", ".supabase_session.json",
                       "interface/data/conversations.db"):
            with self.subTest(chemin=chemin):
                resultat = tools_fichiers.ecrire_fichier(chemin, "REMPLACE")
                self.assertTrue(resultat.startswith("Erreur"), resultat)
                self.assertEqual(self.lire_direct(chemin), MARQUEUR)

    def test_creation_dossier_dans_zone_sensible_refusee(self):
        resultat = tools_fichiers.creer_dossier("memory/sous_dossier")
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertFalse(
            os.path.exists(os.path.join(self.racine, "memory", "sous_dossier"))
        )

    def test_suppression_secrets_refusee(self):
        for chemin in (".env", ".env.bak_20260101",
                       ".supabase_session.json", "memory/memory.json"):
            with self.subTest(chemin=chemin):
                resultat = tools_fichiers.supprimer_fichier(chemin)
                self.assertTrue(resultat.startswith("Erreur"), resultat)
                self.assertTrue(
                    os.path.exists(os.path.join(self.racine, chemin))
                )

    def test_suppression_dossier_sensible_refusee(self):
        for dossier in ("memory", "data", "backups", ".patches"):
            with self.subTest(dossier=dossier):
                resultat = tools_fichiers.supprimer_dossier(dossier)
                self.assertTrue(resultat.startswith("Erreur"), resultat)
                self.assertTrue(
                    os.path.isdir(os.path.join(self.racine, dossier))
                )

    def test_suppression_lien_symbolique_refusee(self):
        lien = os.path.join(self.racine, "lien_env")
        try:
            os.symlink(os.path.join(self.racine, ".env"), lien)
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques indisponibles")

        resultat = tools_fichiers.supprimer_fichier("lien_env")
        self.assertTrue(resultat.startswith("Erreur"))
        self.assertTrue(os.path.exists(lien))
        self.assertTrue(os.path.exists(os.path.join(self.racine, ".env")))

    # ------------------------------------------------------------------
    # Fonctions legitimes
    # ------------------------------------------------------------------
    def test_fichier_ordinaire_reste_lisible_et_modifiable(self):
        self.assertEqual(
            tools_fichiers.lire_fichier("projet/lisible.txt"),
            "CONTENU_PUBLIC",
        )
        resultat = tools_fichiers.ecrire_fichier(
            "projet/lisible.txt", "CONTENU_MODIFIE"
        )
        self.assertNotIn("Erreur", resultat)
        self.assertEqual(
            self.lire_direct("projet/lisible.txt"), "CONTENU_MODIFIE"
        )

    # ------------------------------------------------------------------
    # Aucun contenu sensible transmis au fournisseur IA
    # ------------------------------------------------------------------
    def test_resultat_outil_ne_contient_aucun_secret(self):
        moteur = AIEngine.__new__(AIEngine)
        moteur.derniers_resultats_outils = []
        moteur.action_engagee = False
        moteur.logger = None
        moteur.outils_autorises = ["lire_fichier"]
        moteur.agent_courant = "00_directeur_ia"

        resultat = moteur._executer_outil(
            "lire_fichier", {"chemin": "memory/memory.json"}
        )

        self.assertTrue(str(resultat).startswith("Erreur"))
        self.assertNotIn(MARQUEUR, str(resultat))
        self.assertEqual(len(moteur.derniers_resultats_outils), 1)
        entree = moteur.derniers_resultats_outils[0]
        self.assertEqual(entree["statut"], "echec_execution")
        self.assertNotIn(MARQUEUR, entree["resultat"])


if __name__ == "__main__":
    unittest.main()
