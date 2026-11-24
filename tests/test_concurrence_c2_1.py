"""Tests de concurrence C2-1 bis.

Deux demandes simultanees ne doivent jamais partager l'agent, les outils
autorises, le message d'origine, le mode action, les resultats d'outils
ni l'etat d'action engagee.
"""
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from core.ai_engine import AIEngine


def _creer_moteur():
    """Moteur sans configuration reseau, avec ses ContextVar prets."""
    moteur = AIEngine.__new__(AIEngine)
    moteur.memory_manager = None
    moteur.logger = None
    moteur.providers = {}
    moteur._initialiser_contextvars()
    moteur.derniers_resultats_outils = []
    moteur.action_engagee = False
    moteur.mode_action = False
    return moteur


class _RouteurSynchronise:
    """Faux routeur qui bloque A et B au coeur de demander().

    La barriere garantit que les deux demandes ont deja ecrit leur etat
    avant que l'une ou l'autre ne lise quoi que ce soit.
    """

    def __init__(self, moteur, barriere, actions, observations):
        self.moteur = moteur
        self.barriere = barriere
        self.actions = actions
        self.observations = observations

    def demander(self, message, contexte="", historique=None, on_chunk=None):
        nom = message
        self.barriere.wait(timeout=5)

        self.observations[nom] = {
            "agent": self.moteur.agent_courant,
            "outils": list(self.moteur.outils_autorises or []),
            "message": self.moteur._message_utilisateur_courant,
            "mode_action": self.moteur.mode_action,
            "action_engagee_avant": self.moteur.action_engagee,
            "resultats_avant": list(self.moteur.derniers_resultats_outils),
        }

        outil, arguments = self.actions[nom]
        self.observations[nom]["resultat_outil"] = self.moteur._executer_outil(
            outil, arguments
        )
        self.observations[nom]["action_engagee_apres"] = (
            self.moteur.action_engagee
        )
        self.observations[nom]["resultats_apres"] = list(
            self.moteur.derniers_resultats_outils
        )
        return nom


class TestConcurrenceC2_1(unittest.TestCase):
    def setUp(self):
        self._patchs = [
            patch("core.budget_guard.autorise", return_value=(True, "OK")),
            patch("core.budget_guard.enregistrer_appel", return_value=None),
        ]
        for patch_ in self._patchs:
            patch_.start()
            self.addCleanup(patch_.stop)

    def test_A_B_agents_permissions_messages_et_resultats_isoles(self):
        moteur = _creer_moteur()
        barriere = threading.Barrier(2)
        observations = {}
        erreurs = []

        racine_projet = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        dossier_temp = tempfile.TemporaryDirectory(
            dir=os.path.join(racine_projet, "espace_travail")
        )
        self.addCleanup(dossier_temp.cleanup)
        chemin_a = os.path.join(dossier_temp.name, "dossier_a")
        chemin_b = os.path.join(dossier_temp.name, "fichier_b.txt")
        with open(chemin_b, "w", encoding="utf-8") as fichier:
            fichier.write("contenu B")

        moteur.router = _RouteurSynchronise(
            moteur,
            barriere,
            {
                "A": ("creer_dossier", {"chemin": chemin_a}),
                "B": ("lire_fichier", {"chemin": chemin_b}),
            },
            observations,
        )

        demandes = {
            "A": {
                "agent": "01_developpeur",
                "outils": ["creer_dossier"],
                "message": "message A",
            },
            "B": {
                "agent": "09_securite_ia",
                "outils": ["lire_fichier"],
                "message": "message B",
            },
        }

        def travail(nom):
            try:
                reponse = moteur.demander(
                    nom,
                    outils_autorises=demandes[nom]["outils"],
                    mode_action=True,
                    message_utilisateur_origine=demandes[nom]["message"],
                    agent=demandes[nom]["agent"],
                )
                observations.setdefault(nom, {})["reponse"] = reponse
                # Apres demander, le contexte appelant doit etre restaure
                # (valeurs par defaut du thread), mais pas les resultats.
                observations[nom]["etat_apres"] = {
                    "agent": moteur.agent_courant,
                    "outils": moteur.outils_autorises,
                    "message": moteur._message_utilisateur_courant,
                    "mode_action": moteur.mode_action,
                    "action_engagee": moteur.action_engagee,
                    "resultats": list(moteur.derniers_resultats_outils),
                }
            except BaseException as exc:  # noqa: BLE001 - remonte a l'assertion
                erreurs.append(exc)

        fils = [
            threading.Thread(target=travail, args=(nom,))
            for nom in ("A", "B")
        ]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=15)

        self.assertFalse(any(fil.is_alive() for fil in fils), "thread bloque")
        self.assertEqual(erreurs, [])
        self.assertEqual(set(observations), {"A", "B"})

        a, b = observations["A"], observations["B"]

        # 1. Agent propre a chaque demande.
        self.assertEqual(a["agent"], "01_developpeur")
        self.assertEqual(b["agent"], "09_securite_ia")

        # 2. Outils autorises propres a chaque demande.
        self.assertEqual(a["outils"], ["creer_dossier"])
        self.assertEqual(b["outils"], ["lire_fichier"])

        # 3. Message d'origine propre a chaque demande.
        self.assertEqual(a["message"], "message A")
        self.assertEqual(b["message"], "message B")

        # 4. Mode action isole (les deux le demandent ici).
        self.assertTrue(a["mode_action"])
        self.assertTrue(b["mode_action"])

        # 5. action_engagee : creation pour A, lecture seule pour B.
        self.assertFalse(a["action_engagee_avant"])
        self.assertFalse(b["action_engagee_avant"])
        self.assertTrue(a["action_engagee_apres"])
        self.assertFalse(b["action_engagee_apres"])

        # 6. Resultats d'outils independants.
        self.assertEqual(a["resultats_avant"], [])
        self.assertEqual(b["resultats_avant"], [])
        self.assertEqual(
            [resultat["outil"] for resultat in a["resultats_apres"]],
            ["creer_dossier"],
        )
        self.assertEqual(
            [resultat["outil"] for resultat in b["resultats_apres"]],
            ["lire_fichier"],
        )
        self.assertTrue(a["resultats_apres"][0]["autorise"])
        self.assertTrue(b["resultats_apres"][0]["autorise"])
        self.assertEqual(a["resultats_apres"][0]["statut"], "succes")
        self.assertEqual(b["resultats_apres"][0]["statut"], "succes")
        self.assertTrue(os.path.isdir(chemin_a))

        # Aucune fuite croisee dans les listes de resultats.
        self.assertNotIn(
            "lire_fichier",
            [resultat["outil"] for resultat in a["resultats_apres"]],
        )
        self.assertNotIn(
            "creer_dossier",
            [resultat["outil"] for resultat in b["resultats_apres"]],
        )

        # Restauration du contexte appelant, sans perte des resultats.
        for nom in ("A", "B"):
            etat = observations[nom]["etat_apres"]
            self.assertIsNone(etat["agent"])
            self.assertIsNone(etat["outils"])
            self.assertEqual(etat["message"], "")
            self.assertFalse(etat["mode_action"])
            self.assertEqual(len(etat["resultats"]), 1)
        self.assertTrue(observations["A"]["etat_apres"]["action_engagee"])
        self.assertFalse(observations["B"]["etat_apres"]["action_engagee"])

    def test_deux_instances_ne_partagent_aucune_valeur(self):
        moteur_1 = _creer_moteur()
        moteur_2 = _creer_moteur()

        moteur_1.agent_courant = "agent_1"
        moteur_2.agent_courant = "agent_2"
        moteur_1.outils_autorises = ["creer_dossier"]
        moteur_2.outils_autorises = ["lire_fichier"]
        moteur_1.mode_action = True
        moteur_2.mode_action = False
        moteur_1._message_utilisateur_courant = "message 1"
        moteur_2._message_utilisateur_courant = "message 2"
        moteur_1.action_engagee = True
        moteur_2.action_engagee = False

        # .append() doit rester possible et rester local a l'instance.
        moteur_1.derniers_resultats_outils.append({"outil": "outil_1"})
        moteur_1.derniers_resultats_outils.append({"outil": "outil_2"})

        self.assertEqual(moteur_1.agent_courant, "agent_1")
        self.assertEqual(moteur_2.agent_courant, "agent_2")
        self.assertEqual(moteur_1.outils_autorises, ["creer_dossier"])
        self.assertEqual(moteur_2.outils_autorises, ["lire_fichier"])
        self.assertTrue(moteur_1.mode_action)
        self.assertFalse(moteur_2.mode_action)
        self.assertEqual(moteur_1._message_utilisateur_courant, "message 1")
        self.assertEqual(moteur_2._message_utilisateur_courant, "message 2")
        self.assertTrue(moteur_1.action_engagee)
        self.assertFalse(moteur_2.action_engagee)
        self.assertEqual(
            [r["outil"] for r in moteur_1.derniers_resultats_outils],
            ["outil_1", "outil_2"],
        )
        self.assertEqual(moteur_2.derniers_resultats_outils, [])
        self.assertIsNot(
            moteur_1.derniers_resultats_outils,
            moteur_2.derniers_resultats_outils,
        )
        self.assertIsNot(
            moteur_1._contextvar_pour("agent_courant", None),
            moteur_2._contextvar_pour("agent_courant", None),
        )

    def test_proprietes_append_et_restauration_apres_demander(self):
        moteur = _creer_moteur()
        moteur.agent_courant = "agent_externe"
        moteur.outils_autorises = ["outil_externe"]
        moteur.mode_action = True
        moteur._message_utilisateur_courant = "message externe"
        moteur.derniers_resultats_outils.append({"outil": "resultat_externe"})

        vus = {}

        class RouteurSimple:
            def demander(self, message, contexte="", historique=None, on_chunk=None):
                vus["agent"] = moteur.agent_courant
                vus["outils"] = moteur.outils_autorises
                vus["message"] = moteur._message_utilisateur_courant
                vus["mode_action"] = moteur.mode_action
                moteur.derniers_resultats_outils.append(
                    {"outil": "resultat_demande"}
                )
                return "ok"

        moteur.router = RouteurSimple()

        resultat = moteur.demander(
            "nouveau message",
            outils_autorises=["nouvel_outil"],
            mode_action=False,
            agent="nouvel_agent",
        )

        self.assertEqual(resultat, "ok")
        self.assertEqual(vus["agent"], "nouvel_agent")
        self.assertEqual(vus["outils"], ["nouvel_outil"])
        self.assertEqual(vus["message"], "nouveau message")
        self.assertFalse(vus["mode_action"])

        self.assertEqual(moteur.agent_courant, "agent_externe")
        self.assertEqual(moteur.outils_autorises, ["outil_externe"])
        self.assertEqual(moteur._message_utilisateur_courant, "message externe")
        self.assertTrue(moteur.mode_action)
        # La demande repart d'une liste neuve : le resultat externe
        # n'est pas conserve, comme avant le correctif.
        self.assertEqual(
            [r["outil"] for r in moteur.derniers_resultats_outils],
            ["resultat_demande"],
        )


if __name__ == "__main__":
    unittest.main()
