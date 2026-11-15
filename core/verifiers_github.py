"""Verificateurs GitHub - extraits de verifiers.py."""
import os
import re

from core.tools import (
    github_creer_repo, github_ecrire_fichier,
    github_lire_fichier, github_lister_repos,
)


class VerifiersGithubMixin:
    """Mixin fournissant les verificateurs GitHub."""

    def _verifier_github_ecrire_fichier(self, arguments, resultat):
        # Relit le fichier sur GitHub et compare exactement au contenu demande.
        import base64
        import json
        import subprocess
        import time

        if isinstance(resultat, str) and resultat.startswith("Erreur"):
            return {"verifie": False, "details": f"L'ecriture GitHub a echoue : {resultat}"}

        repo = arguments.get("repo")
        chemin = arguments.get("chemin")
        contenu = arguments.get("contenu")
        if (not isinstance(repo, str) or not repo.strip()
                or not isinstance(chemin, str) or not chemin.strip()
                or not isinstance(contenu, str)):
            return {"verifie": False, "details": "Verification impossible : repo, chemin ou contenu absent des arguments."}

        repo = repo.strip()
        chemin = chemin.strip()

        try:
            if "/" not in repo:
                p = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                                   capture_output=True, text=True, timeout=15, check=False)
                login = p.stdout.strip()
                if p.returncode != 0 or not login:
                    return {"verifie": False, "details": "Verification impossible : compte GitHub introuvable."}
                repo = f"{login}/{repo}"

            raison = ""
            for tentative in range(2):
                if tentative > 0:
                    time.sleep(2)
                lecture = subprocess.run(["gh", "api", f"repos/{repo}/contents/{chemin}"],
                                         capture_output=True, text=True, timeout=15, check=False)
                if lecture.returncode != 0:
                    raison = "Lecture GitHub echouee : " + (lecture.stderr.strip() or lecture.stdout.strip() or "erreur inconnue")
                    continue
                donnees = json.loads(lecture.stdout)
                if not isinstance(donnees, dict) or donnees.get("type") != "file":
                    return {"verifie": False, "details": "Le chemin n'est pas un fichier sur GitHub."}
                if donnees.get("encoding") != "base64":
                    return {"verifie": False, "details": "Verification impossible : contenu non fourni en base64 (fichier trop gros ?)."}
                distant = base64.b64decode(donnees.get("content", "")).decode("utf-8")
                if distant == contenu:
                    return {"verifie": True, "details": f"Le contenu de {repo}/{chemin} a ete relu sur GitHub et correspond exactement."}
                raison = "Le contenu present sur GitHub differe du contenu demande."
            return {"verifie": False, "details": raison}
        except FileNotFoundError:
            return {"verifie": False, "details": "Verification impossible : GitHub CLI 'gh' introuvable."}
        except subprocess.TimeoutExpired:
            return {"verifie": False, "details": "Verification impossible : lecture GitHub expiree."}
        except ValueError as e:
            return {"verifie": False, "details": f"Reponse GitHub illisible : {type(e).__name__}: {e}"}
        except OSError as e:
            return {"verifie": False, "details": f"Erreur systeme pendant la verification : {type(e).__name__}: {e}"}


    def _verifier_github_creer_repo(self, arguments, resultat):
        """
        Verifie independamment qu'un depot GitHub existe
        avec la visibilite demandee.
        """
        import json
        import subprocess

        if isinstance(resultat, str) and resultat.startswith("Erreur"):
            return {
                "verifie": False,
                "details": f"La creation du depot a echoue : {resultat}"
            }

        nom = arguments.get("nom")
        public = arguments.get("public", True)

        if not isinstance(nom, str) or not nom.strip():
            return {
                "verifie": False,
                "details": "Verification impossible : nom du depot absent."
            }

        if not isinstance(public, bool):
            return {
                "verifie": False,
                "details": "Verification impossible : public doit etre booleen."
            }

        try:
            verification = subprocess.run(
                [
                    "gh",
                    "repo",
                    "view",
                    nom.strip(),
                    "--json",
                    "nameWithOwner,url,isPrivate",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            return {
                "verifie": False,
                "details": "Verification impossible : GitHub CLI 'gh' est introuvable."
            }
        except subprocess.TimeoutExpired:
            return {
                "verifie": False,
                "details": "Verification GitHub expiree."
            }
        except OSError as erreur:
            return {
                "verifie": False,
                "details": (
                    "Erreur systeme pendant la verification GitHub : "
                    f"{type(erreur).__name__}: {erreur}"
                )
            }

        if verification.returncode != 0:
            details = (
                verification.stderr.strip()
                or verification.stdout.strip()
                or "aucun detail fourni"
            )
            return {
                "verifie": False,
                "details": (
                    "Le depot GitHub n'a pas pu etre relu : "
                    f"{details}"
                )
            }

        try:
            depot = json.loads(verification.stdout)
        except json.JSONDecodeError as erreur:
            return {
                "verifie": False,
                "details": (
                    "Reponse GitHub invalide pendant la verification : "
                    f"{erreur}"
                )
            }

        est_prive = depot.get("isPrivate")
        visibilite_attendue = not public

        if est_prive != visibilite_attendue:
            visibilite = "prive" if est_prive else "public"
            attendue = "prive" if not public else "public"
            return {
                "verifie": False,
                "details": (
                    f"Le depot existe mais sa visibilite est {visibilite}; "
                    f"la demande exige {attendue}."
                )
            }

        return {
            "verifie": True,
            "details": (
                "Le depot GitHub a ete relu independamment avec gh et "
                "correspond a la visibilite demandee : "
                f"{depot.get('nameWithOwner', nom)} "
                f"({depot.get('url', 'URL inconnue')})."
            )
        }

