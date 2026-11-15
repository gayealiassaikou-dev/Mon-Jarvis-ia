"""Verificateurs de resultats d'outils pour Jarvis - extrait de ai_engine.py."""
import os
import re

from core.tools import (
    ecrire_fichier, lire_fichier, github_creer_repo, github_ecrire_fichier,
    github_lire_fichier, github_lister_repos, lire_etat_projets_taches,
)
from core.outils_telephone import FONCTIONS_TELEPHONE
from core.verifiers_github import VerifiersGithubMixin


class VerifiersMixin(VerifiersGithubMixin):
    """Methodes de verification post-execution (fichiers, GitHub, resultats)."""

    def _verifier_resultat_outil(self, nom_fonction, arguments, resultat):
        """
        Verifie reellement le resultat d'une action executee par un outil.

        Pour l'instant, ecrire_fichier et creer_dossier disposent d'une
        verification specifique.
        Les autres outils restent inchanges jusqu'a leur audit individuel.
        """

        if nom_fonction in FONCTIONS_TELEPHONE:
            return verifier_action_telephone(nom_fonction, resultat)

        if nom_fonction == "gerer_musique":
            if not isinstance(resultat, str):
                return {
                    "verifie": False,
                    "details": "Le resultat de la gestion musicale n'est pas du texte."
                }

            prefixe_local = "Morceau envoyé au lecteur Android : "
            if resultat.startswith(prefixe_local):
                morceau = resultat[len(prefixe_local):].strip()
                if morceau:
                    return {
                        "verifie": True,
                        "details": (
                            "Android a accepté la commande d'ouverture du lecteur "
                            "pour le morceau : " + morceau
                        )
                    }

                return {
                    "verifie": False,
                    "details": "Le nom du morceau envoyé au lecteur est absent."
                }

            if resultat.startswith("Recherche de ") and " ouverte avec " in resultat:
                return {
                    "verifie": True,
                    "details": "La demande d'ouverture de la recherche musicale a été acceptée."
                }

            if resultat.startswith("Erreur") or resultat.startswith("Impossible"):
                return {
                    "verifie": False,
                    "details": "L'action musicale a échoué : " + resultat
                }

            return {
                "verifie": False,
                "details": "Aucune confirmation valide du lancement musical : " + resultat
            }

        if nom_fonction == "github_ecrire_fichier":
            return self._verifier_github_ecrire_fichier(arguments, resultat)

        if nom_fonction == "github_creer_repo":
            return self._verifier_github_creer_repo(arguments, resultat)

        if nom_fonction == "executer_programme_python":
            if not isinstance(resultat, str):
                return {
                    "verifie": False,
                    "details": "Le resultat de l'execution Python n'est pas du texte."
                }

            premiere_ligne = resultat.splitlines()[0] if resultat.splitlines() else ""

            if premiere_ligne.startswith("SUCCES :") and "code 0" in premiere_ligne:
                return {
                    "verifie": True,
                    "details": "Le programme Python s'est termine avec le code 0."
                }

            if premiere_ligne.startswith("ECHEC :"):
                return {
                    "verifie": False,
                    "details": f"Le programme Python a echoue : {premiere_ligne}"
                }

            return {
                "verifie": False,
                "details": "Le resultat de l'execution Python est inattendu."
            }

        if nom_fonction == "creer_dossier":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La creation du dossier a echoue : {resultat}"
                }

            chemin = arguments.get("chemin")

            if not chemin:
                return {
                    "verifie": False,
                    "details": "Verification impossible : chemin absent des arguments."
                }

            chemin_reel = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), chemin)))

            if not os.path.exists(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le dossier demande n'existe pas apres sa creation."
                }

            if not os.path.isdir(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le chemin existe apres l'action mais ce n'est pas un dossier."
                }

            return {
                "verifie": True,
                "details": "Le dossier a ete verifie physiquement et existe bien."
            }
        if nom_fonction in {
            "lire_fichier",
            "lister_fichiers",
            "lister_projets",
            "lister_taches",
        }:
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"{nom_fonction} a retourne une erreur : {resultat}",
                }
            if not isinstance(resultat, str):
                return {
                    "verifie": False,
                    "details": (
                        f"{nom_fonction} a retourne un type invalide : "
                        f"{type(resultat).__name__}."
                    ),
                }
            return {
                "verifie": True,
                "details": (
                    f"{nom_fonction} execute avec succes ; "
                    "le resultat respecte le contrat de lecture."
                ),
            }

        if nom_fonction in {
            "github_lire_fichier",
            "github_lister_repos",
            "rechercher_web",
        }:
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": (
                        f"{nom_fonction} a retourne une erreur : "
                        f"{resultat}"
                    ),
                }

            if not isinstance(resultat, str):
                return {
                    "verifie": False,
                    "details": (
                        f"{nom_fonction} a retourne un type invalide : "
                        f"{type(resultat).__name__}."
                    ),
                }

            return {
                "verifie": True,
                "details": (
                    f"{nom_fonction} execute avec succes ; "
                    "le resultat respecte le contrat de lecture externe."
                ),
            }

        if nom_fonction == "supprimer_tache":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de suppression a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom de la tache absent des arguments."
                }

            etat = lire_etat_projets_taches()
            taches = etat.get("taches", [])

            existe = any(
                isinstance(t, dict)
                and t.get("nom", "").strip().lower() == nom.strip().lower()
                for t in taches
            )

            if existe:
                return {
                    "verifie": False,
                    "details": "La tache existe encore apres la suppression."
                }

            return {
                "verifie": True,
                "details": "La tache a ete verifiee et n'existe plus."
            }

        if nom_fonction == "supprimer_projet":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de suppression a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom du projet absent des arguments."
                }

            etat = lire_etat_projets_taches()
            projets = etat.get("projets", [])

            import unicodedata
            from difflib import SequenceMatcher

            def normaliser_nom(valeur):
                texte = unicodedata.normalize("NFKD", str(valeur or "").strip().casefold())
                texte = "".join(c for c in texte if not unicodedata.combining(c))
                return " ".join(texte.split())

            nom_normalise = normaliser_nom(nom)
            noms_existants = [
                p.get("nom", "").strip()
                for p in projets
                if isinstance(p, dict) and isinstance(p.get("nom"), str)
            ]

            existe = any(
                normaliser_nom(nom_existant) == nom_normalise
                for nom_existant in noms_existants
            )

            if existe:
                return {
                    "verifie": False,
                    "details": "Le projet existe encore apres la suppression."
                }

            ressemblances = [
                nom_existant for nom_existant in noms_existants
                if SequenceMatcher(
                    None, nom_normalise, normaliser_nom(nom_existant)
                ).ratio() >= 0.70
            ]

            if ressemblances:
                return {
                    "verifie": False,
                    "details": (
                        "Suppression non confirmee : le nom recherche ne correspond "
                        "pas exactement a un projet supprime. Projet(s) ressemblant(s) "
                        "encore present(s) : " + ", ".join(ressemblances)
                    )
                }

            return {
                "verifie": True,
                "details": "Le projet a ete verifie et n'existe plus."
            }

        if nom_fonction == "ajouter_tache":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'ajout de la tache a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            projet = arguments.get("projet", "")

            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom de la tache absent des arguments."
                }

            etat = lire_etat_projets_taches()
            taches = etat.get("taches", [])

            for tache in taches:
                if not isinstance(tache, dict):
                    continue

                meme_nom = tache.get("nom", "").strip().lower() == nom.strip().lower()
                meme_projet = tache.get("projet", "").strip().lower() == projet.strip().lower()

                if meme_nom and meme_projet:
                    statut = tache.get("statut", "").strip().lower()

                    if statut == "en attente":
                        return {
                            "verifie": True,
                            "details": "La tache a ete relue dans l'etat structure et existe avec le statut 'en attente'."
                        }

                    return {
                        "verifie": False,
                        "details": f"La tache existe mais son statut est '{statut}' au lieu de 'en attente'."
                    }

            return {
                "verifie": False,
                "details": "La tache n'existe pas lors de la verification apres son ajout."
            }

        if nom_fonction == "creer_projet":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La creation du projet a echoue : {resultat}"
                }

            nom = arguments.get("nom")

            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom du projet absent des arguments."
                }

            etat = lire_etat_projets_taches()
            projets = etat.get("projets", [])

            for projet in projets:
                if not isinstance(projet, dict):
                    continue

                if projet.get("nom", "").strip().lower() == nom.strip().lower():
                    statut = projet.get("statut", "").strip().lower()

                    if statut == "en cours":
                        return {
                            "verifie": True,
                            "details": "Le projet a ete relu dans l'etat structure et existe avec le statut 'en cours'."
                        }

                    return {
                        "verifie": False,
                        "details": f"Le projet existe mais son statut est '{statut}' au lieu de 'en cours'."
                    }

            return {
                "verifie": False,
                "details": "Le projet n'existe pas lors de la verification apres sa creation."
            }

        if nom_fonction == "modifier_statut_projet":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La modification du statut a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            nouveau_statut = arguments.get("nouveau_statut")

            if (
                not isinstance(nom, str) or not nom.strip()
                or not isinstance(nouveau_statut, str) or not nouveau_statut.strip()
            ):
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom ou nouveau statut absent des arguments."
                }

            nom_recherche = nom.strip().lower()
            statut_attendu = nouveau_statut.strip().lower()

            etat = lire_etat_projets_taches()
            projets = etat.get("projets", [])

            for projet in projets:
                if not isinstance(projet, dict):
                    continue

                if projet.get("nom", "").strip().lower() == nom_recherche:
                    statut = projet.get("statut", "").strip().lower()

                    if statut == statut_attendu:
                        return {
                            "verifie": True,
                            "details": "Le projet a ete relu dans l'etat structure et son statut correspond au statut demande."
                        }

                    return {
                        "verifie": False,
                        "details": f"Le projet existe mais son statut est '{statut}' au lieu de '{statut_attendu}'."
                    }

            return {
                "verifie": False,
                "details": "Le projet est introuvable lors de la verification."
            }

        if nom_fonction == "terminer_tache":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de terminaison a echoue : {resultat}"
                }

            nom = arguments.get("nom")

            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom de la tache absent des arguments."
                }

            etat = lire_etat_projets_taches()
            taches = etat.get("taches", [])

            for tache in taches:
                if not isinstance(tache, dict):
                    continue

                if tache.get("nom", "").strip().lower() == nom.strip().lower():
                    statut = tache.get("statut", "").strip().lower()

                    if statut == "terminee":
                        return {
                            "verifie": True,
                            "details": "La tache a ete relue dans l'etat structure et son statut est bien terminee."
                        }

                    return {
                        "verifie": False,
                        "details": f"La tache existe mais son statut est '{statut}' au lieu de 'terminee'."
                    }

            return {
                "verifie": False,
                "details": "La tache est introuvable lors de la verification."
            }

        if nom_fonction == "supprimer_fichier":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de suppression a echoue : {resultat}"
                }

            chemin = arguments.get("chemin")

            if not chemin:
                return {
                    "verifie": False,
                    "details": "Verification impossible : chemin absent des arguments."
                }

            chemin_reel = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), chemin)))

            if os.path.exists(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le fichier existe encore apres la suppression."
                }

            return {
                "verifie": True,
                "details": "Le fichier a ete verifie physiquement et n'existe plus."
            }


        if nom_fonction == "supprimer_dossier":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La suppression du dossier a echoue : {resultat}"
                }

            chemin = arguments.get("chemin")
            if not isinstance(chemin, str) or not chemin.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : chemin du dossier absent."
                }

            racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            chemin_reel = os.path.realpath(os.path.abspath(os.path.join(racine, chemin)))

            if os.path.exists(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le dossier existe encore apres la suppression."
                }

            return {
                "verifie": True,
                "details": "La disparition du dossier a ete verifiee physiquement."
            }

        if nom_fonction == "definir_projet_actif":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La selection du projet a echoue : {resultat}"
                }

            prefixe = "Projet actif selectionne : "
            if not isinstance(resultat, str) or not resultat.startswith(prefixe):
                return {
                    "verifie": False,
                    "details": "La selection du projet n'a pas retourne de confirmation valide."
                }

            nom_selectionne = resultat[len(prefixe):].rstrip(".").strip()
            if not nom_selectionne:
                return {
                    "verifie": False,
                    "details": "Le nom du projet selectionne est absent."
                }

            projet_relu = obtenir_projet_actif()
            confirmation_attendue = f"Projet actif : {nom_selectionne}."

            if projet_relu == confirmation_attendue:
                return {
                    "verifie": True,
                    "details": "Le projet actif a ete relu depuis le fichier et correspond a la selection."
                }

            return {
                "verifie": False,
                "details": f"La verification du projet actif a echoue : {projet_relu}"
            }

        if nom_fonction != "ecrire_fichier":
            return {
                "verifie": None,
                "details": "Aucune verification specifique disponible pour cet outil."
            }

        # Si l'action elle-meme a echoue, inutile de tenter une seconde
        # operation de lecture pour verifier son resultat.
        if isinstance(resultat, str) and resultat.startswith("Erreur"):
            return {
                "verifie": False,
                "details": f"L'action d'ecriture a echoue : {resultat}"
            }

        chemin = arguments.get("chemin")
        contenu_attendu = arguments.get("contenu")

        if not chemin:
            return {
                "verifie": False,
                "details": "Verification impossible : chemin absent des arguments."
            }

        if contenu_attendu is None:
            return {
                "verifie": False,
                "details": "Verification impossible : contenu absent des arguments."
            }

        contenu_lu = lire_fichier(chemin)

        if contenu_lu.startswith("Erreur"):
            return {
                "verifie": False,
                "details": f"Lecture de verification echouee : {contenu_lu}"
            }

        if contenu_lu != contenu_attendu:
            return {
                "verifie": False,
                "details": "Le contenu relu ne correspond pas au contenu demande."
            }

        return {
            "verifie": True,
            "details": "Le fichier a ete relu et son contenu correspond exactement a la demande."
        }

