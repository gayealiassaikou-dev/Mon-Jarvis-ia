import os
import tempfile
import unittest
from unittest.mock import Mock

from core.ai_engine import AIEngine
from core.agent_permissions import PERMISSIONS_AGENTS, TOUS_LES_OUTILS
from core.tool_guard import (
    STATUT_NON_AUTORISE,
    STATUT_OUTIL_INCONNU,
    filtrer_outils_pour_agent,
    outil_connu,
    verifier_execution,
)


class TestToolGuard(unittest.TestCase):
    def test_outils_connus(self):
        for nom in ("lire_fichier", "ecrire_fichier", "creer_site_web",
                    "memoriser_info", "rechercher_souvenir", "lire_batterie"):
            self.assertTrue(outil_connu(nom), nom)

    def test_outil_inconnu_refuse(self):
        verdict = verifier_execution("outil_imaginaire", ["outil_imaginaire"])
        self.assertFalse(verdict["autorise"])
        self.assertEqual(verdict["statut"], STATUT_OUTIL_INCONNU)

    def test_deny_by_default_sans_liste(self):
        for liste in (None, [], (), set()):
            verdict = verifier_execution("lire_fichier", liste)
            self.assertFalse(verdict["autorise"], liste)
            self.assertEqual(verdict["statut"], STATUT_NON_AUTORISE)
            self.assertEqual(verdict["code"], "aucun_outil_autorise")

    def test_outil_absent_de_la_liste_refuse(self):
        verdict = verifier_execution("ecrire_fichier", ["lire_fichier"])
        self.assertFalse(verdict["autorise"])
        self.assertEqual(verdict["code"], "outil_non_liste")

    def test_agent_sans_permission_refuse_meme_si_liste_explicite(self):
        # 09_securite_ia ne peut ni ecrire ni creer de dossier.
        verdict = verifier_execution(
            "creer_dossier",
            ["creer_dossier"],
            agent="09_securite_ia",
        )
        self.assertFalse(verdict["autorise"])
        self.assertEqual(verdict["code"], "hors_permissions_agent")

    def test_agent_avec_permission_accepte(self):
        verdict = verifier_execution(
            "creer_dossier",
            ["creer_dossier"],
            agent="01_developpeur",
        )
        self.assertTrue(verdict["autorise"])
        self.assertEqual(verdict["statut"], "autorise")

    def test_agent_inconnu_refuse(self):
        verdict = verifier_execution(
            "lire_fichier",
            ["lire_fichier"],
            agent="99_agent_inexistant",
        )
        self.assertFalse(verdict["autorise"])
        self.assertEqual(verdict["code"], "agent_inconnu")

    def test_directeur_a_tous_les_outils(self):
        verdict = verifier_execution(
            "supprimer_dossier",
            ["supprimer_dossier"],
            agent="00_directeur_ia",
        )
        self.assertTrue(verdict["autorise"])

    def test_filtrer_outils_pour_agent(self):
        filtres = filtrer_outils_pour_agent(
            "03_recherche",
            ["lire_fichier", "ecrire_fichier", "rechercher_web", "inconnu"],
        )
        self.assertEqual(filtres, ["lire_fichier", "rechercher_web"])

    def test_filtrer_agent_inconnu_ne_laisse_rien_passer(self):
        self.assertEqual(
            filtrer_outils_pour_agent("99_agent_inexistant", TOUS_LES_OUTILS),
            [],
        )
        self.assertEqual(filtrer_outils_pour_agent(None, ["lire_fichier"]), [])

    def test_permissions_declarees_coherentes(self):
        for agent in PERMISSIONS_AGENTS:
            inconnus = [o for o in PERMISSIONS_AGENTS[agent] if not outil_connu(o)]
            self.assertEqual(inconnus, [], agent)


class TestAIEngineGardeFou(unittest.TestCase):
    def setUp(self):
        self.moteur = AIEngine.__new__(AIEngine)
        self.moteur.derniers_resultats_outils = []
        self.moteur.action_engagee = False
        self.moteur.logger = None
        self.moteur.outils_autorises = ["creer_dossier"]
        self.moteur.agent_courant = "09_securite_ia"
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.chemin = os.path.join(self.temp.name, "dossier_refuse")

    def test_execution_refusee_avant_effet_de_bord(self):
        resultat = self.moteur._executer_outil(
            "creer_dossier", {"chemin": self.chemin}
        )

        self.assertTrue(str(resultat).startswith("Erreur"))
        self.assertFalse(os.path.exists(self.chemin))
        self.assertEqual(len(self.moteur.derniers_resultats_outils), 1)
        entree = self.moteur.derniers_resultats_outils[0]
        self.assertEqual(entree["statut"], "non_autorise")
        self.assertFalse(entree["autorise"])
        self.assertFalse(entree["execute"])

    def test_liste_vide_refusee(self):
        self.moteur.outils_autorises = []
        resultat = self.moteur._executer_outil(
            "creer_dossier", {"chemin": self.chemin}
        )
        self.assertTrue(str(resultat).startswith("Erreur"))
        self.assertFalse(os.path.exists(self.chemin))
        self.assertEqual(
            self.moteur.derniers_resultats_outils[0]["statut"],
            "non_autorise",
        )

    def test_agent_transmis_et_restaure_par_demander(self):
        self.moteur.router = Mock()
        self.moteur.router.demander.return_value = "ok"
        self.moteur.agent_courant = "agent_precedent"

        resultat = self.moteur.demander(
            "bonjour",
            outils_autorises=["lire_fichier"],
            agent="03_recherche",
        )

        self.assertEqual(resultat, "ok")
        self.assertEqual(self.moteur.agent_courant, "agent_precedent")
        self.assertEqual(self.moteur.outils_autorises, ["creer_dossier"])


if __name__ == "__main__":
    unittest.main()
