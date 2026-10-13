import unittest
from unittest.mock import patch

import core.ai_engine as moteur

FOURNISSEURS = ["mistral", "openrouter", "groq", "gemini"]


class TestRouteurLectureSeule(unittest.TestCase):
    def setUp(self):
        self.moteur = moteur.AIEngine()
        self.appels_outil = []
        self.appels_fournisseurs = []

    def outil_lecture(self, **kwargs):
        self.appels_outil.append(kwargs)
        return "contenu liste"

    def lit_puis_plante(self, nom, erreur):
        def faux(message, contexte="", historique=None):
            self.appels_fournisseurs.append(nom)
            self.moteur._executer_outil("lister_fichiers", {"dossier": "."})
            raise Exception(erreur)
        return faux

    def repond(self, nom, texte):
        def faux(message, contexte="", historique=None):
            self.appels_fournisseurs.append(nom)
            return texte
        return faux

    def plante(self, nom, erreur):
        def faux(message, contexte="", historique=None):
            self.appels_fournisseurs.append(nom)
            raise Exception(erreur)
        return faux

    def installer(self, faux_par_nom):
        for nom in FOURNISSEURS:
            faux = faux_par_nom.get(nom) or self.plante(nom, "erreur de test")
            p = patch.object(self.moteur, "_demander_" + nom, faux)
            p.start()
            self.addCleanup(p.stop)

    def lancer(self):
        with patch.dict(moteur.FONCTIONS_DISPONIBLES,
                        {"lister_fichiers": self.outil_lecture}):
            return self.moteur.demander(
                "liste le dossier",
                outils_autorises=["lister_fichiers"],
                mode_action=True,
            )

    def test_fallback_apres_lecture_puis_429(self):
        ordre = self.moteur.router.fournisseurs
        premier, second = ordre[:2]
        self.installer({
            premier: self.lit_puis_plante(premier, "429 Too Many Requests"),
            second: self.repond(second, "reponse de secours"),
        })
        reponse = self.lancer()
        # L'outil de lecture a bien tourne (sinon le test ne prouve rien).
        self.assertEqual(len(self.appels_outil), 1)
        # Lecture seule : le routeur doit passer au fournisseur suivant.
        self.assertEqual(self.appels_fournisseurs, [premier, second])
        self.assertEqual(reponse, "reponse de secours")


if __name__ == "__main__":
    unittest.main()
