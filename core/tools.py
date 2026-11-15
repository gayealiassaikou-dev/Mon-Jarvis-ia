import unicodedata
import os
import difflib
import re
import json
import requests
import base64
import shutil

DOSSIER_AUTORISE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Outils fichiers deplaces dans core/tools_fichiers.py
from core.tools_fichiers import (  # noqa: F401
    _chemin_autorise, _fichier_protege, _normaliser_nom_chemin,
    _chercher_dossiers_similaires, creer_parent_manquant_pour_ecriture,
    lire_fichier, ecrire_fichier, supprimer_fichier, supprimer_dossier,
    lister_fichiers_original_en_ligne, lister_fichiers, creer_dossier,
)

from core.tools_web import rechercher_web  # noqa: F401

from core.tools_github import (  # noqa: F401
    _headers_github, _interpreter_erreur_github,
    github_creer_repo_original_en_ligne, github_creer_repo,
    github_lister_repos_original_en_ligne, github_lister_repos,
    _github_resoudre_repo, _github_entetes, _github_message_erreur,
    github_lire_fichier_original_en_ligne, github_lire_fichier,
    github_ecrire_fichier_original_en_ligne, github_ecrire_fichier,
)

from core.tools_projets import (  # noqa: F401
    CHEMIN_DONNEES, CHEMIN_PROJET_ACTIF,
    _charger_donnees, _sauvegarder_donnees,
    lire_etat_projets_taches, creer_projet, ajouter_tache,
    lister_projets, definir_projet_actif, _obtenir_nom_projet_actif,
    obtenir_projet_actif, lister_taches,
    terminer_tache, supprimer_tache, supprimer_projet, modifier_statut_projet,
)

def analyser_erreur_python(traceback):
    """Analyse un traceback et affiche le code autour de l'erreur."""
    import re

    if not isinstance(traceback, str) or not traceback.strip():
        return "Erreur : aucun traceback fourni."

    texte = traceback.strip()
    correspondances = re.findall(
        r'File "([^"]+)", line (\d+)',
        texte
    )
    exception = re.search(
        r"^([A-Za-z_][A-Za-z0-9_.]*):\s*(.*)$",
        texte,
        re.MULTILINE
    )

    if not exception:
        return "Diagnostic incomplet : type d'erreur Python introuvable.\n" + texte[-4000:]

    type_erreur = exception.group(1).split(".")[-1]
    message = exception.group(2).strip()

    explications = {
        "ZeroDivisionError": "Une division a ete effectuee par zero.",
        "NameError": "Une variable ou un nom utilise n'est pas defini.",
        "TypeError": "Une operation a recu un type de donnee incompatible.",
        "IndexError": "Le programme tente d'acceder a un element hors des limites d'une liste ou sequence.",
        "KeyError": "Une cle demandee est absente d'un dictionnaire.",
        "AttributeError": "Un objet ne possede pas l'attribut ou la methode utilisee.",
        "FileNotFoundError": "Un fichier ou dossier demande est introuvable.",
        "ModuleNotFoundError": "Un module Python necessaire est introuvable.",
        "ImportError": "Un element necessaire n'a pas pu etre importe.",
        "ValueError": "Une valeur est incompatible avec l'operation demandee.",
        "PermissionError": "Le programme ne dispose pas des permissions necessaires.",
        "IndentationError": "L'indentation du code Python est incorrecte.",
        "SyntaxError": "Le code contient une erreur de syntaxe."
    }

    lignes = [
        "DIAGNOSTIC PYTHON",
        f"Type : {type_erreur}",
        f"Message : {message or 'Aucun detail fourni.'}",
        f"Cause probable : {explications.get(type_erreur, 'Une exception Python est survenue. Une analyse du code concerne est necessaire.')}"
    ]

    if correspondances:
        fichier_erreur, numero = correspondances[-1]
        numero = int(numero)
        lignes.extend([
            f"Fichier : {fichier_erreur}",
            f"Ligne : {numero}"
        ])

        racine = os.path.realpath(DOSSIER_AUTORISE)
        dossier_travail = os.path.realpath(os.path.join(racine, "espace_travail"))
        chemin_reel = os.path.realpath(fichier_erreur)

        try:
            dans_espace = os.path.commonpath(
                [chemin_reel, dossier_travail]
            ) == dossier_travail
        except ValueError:
            dans_espace = False

        if (
            dans_espace
            and chemin_reel.endswith(".py")
            and _chemin_autorise(chemin_reel)
            and not _fichier_protege(chemin_reel)
            and os.path.isfile(chemin_reel)
        ):
            try:
                with open(chemin_reel, "r", encoding="utf-8") as source:
                    contenu = source.readlines()

                if 1 <= numero <= len(contenu):
                    debut = max(1, numero - 5)
                    fin = min(len(contenu), numero + 5)
                    lignes.append("CONTEXTE DU CODE :")
                    for index in range(debut, fin + 1):
                        marqueur = ">" if index == numero else " "
                        lignes.append(
                            f"{marqueur} {index:4}: {contenu[index - 1].rstrip()}"
                        )
                else:
                    lignes.append("Contexte indisponible : numero de ligne invalide.")
            except (OSError, UnicodeError) as exc:
                lignes.append(f"Contexte indisponible : {exc}")
        else:
            lignes.append(
                "Contexte non lu : fichier hors de l'espace de travail autorise."
            )

    lignes.append(
        "Correction : a determiner en examinant le code et le contexte ci-dessus."
    )
    return "\\n".join(lignes)

def diagnostiquer_code_python(chemin):
    """Analyse la syntaxe Python sans executer le programme."""
    import ast

    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : chemin absent."

    complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin.strip()))
    reel = os.path.realpath(complet)

    if not _chemin_autorise(complet) or not _chemin_autorise(reel):
        return "Erreur : chemin en dehors du projet."

    if not reel.endswith(".py") or not os.path.isfile(reel):
        return "Erreur : fichier Python introuvable."

    try:
        with open(reel, "r", encoding="utf-8") as fichier:
            source = fichier.read()
        ast.parse(source, filename=reel)
        compile(source, reel, "exec")
        return f"SUCCES : aucune erreur de syntaxe dans {chemin}."
    except SyntaxError as exc:
        return (
            f"ERREUR DE SYNTAXE : {exc.msg}\n"
            f"Fichier : {chemin}\n"
            f"Ligne : {exc.lineno}\n"
            f"Colonne : {exc.offset}"
        )
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Erreur de diagnostic : {exc}"



def _cible_python_espace_travail(chemin):
    """Valide une cible Python située dans espace_travail."""
    if not isinstance(chemin, str) or not chemin.strip():
        return None, None, "Erreur : chemin absent."

    dossier = os.path.realpath(
        os.path.join(DOSSIER_AUTORISE, "espace_travail")
    )
    complet = os.path.abspath(
        os.path.join(DOSSIER_AUTORISE, chemin.strip())
    )
    reel = os.path.realpath(complet)

    try:
        autorise = (
            os.path.commonpath([complet, dossier]) == dossier
            and os.path.commonpath([reel, dossier]) == dossier
        )
    except ValueError:
        autorise = False

    if not autorise:
        return None, None, "Erreur : fichier hors de espace_travail."

    if not _chemin_autorise(reel) or _fichier_protege(reel):
        return None, None, "Erreur : accès refusé."

    if not reel.endswith(".py") or not os.path.isfile(reel):
        return None, None, "Erreur : fichier Python introuvable."

    relatif = os.path.relpath(reel, DOSSIER_AUTORISE)
    return reel, relatif, None


def corriger_code_python(chemin, ancien_code, nouveau_code):
    """Remplace une occurrence exacte après validation syntaxique."""
    import ast

    reel, relatif, erreur = _cible_python_espace_travail(chemin)
    if erreur:
        return erreur

    if not isinstance(ancien_code, str) or not ancien_code:
        return "Erreur : ancien code absent ou invalide."

    if not isinstance(nouveau_code, str):
        return "Erreur : nouveau code invalide."

    try:
        with open(reel, "r", encoding="utf-8") as fichier:
            source = fichier.read()

        occurrences = source.count(ancien_code)
        if occurrences == 0:
            return "Erreur : ancien code introuvable. Aucune modification."
        if occurrences > 1:
            return f"Erreur : {occurrences} occurrences trouvées. Correction refusée."

        corrige = source.replace(ancien_code, nouveau_code, 1)

        ast.parse(corrige, filename=reel)
        compile(corrige, reel, "exec")

        return ecrire_fichier(relatif, corrige)

    except SyntaxError as exc:
        return (
            f"Correction refusée : erreur de syntaxe à la ligne "
            f"{exc.lineno} : {exc.msg}"
        )
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Erreur pendant la correction : {exc}"


def reparer_syntaxe_python(chemin):
    """Répare uniquement un deux-points manquant sur une ligne reconnue."""
    import ast

    reel, relatif, erreur = _cible_python_espace_travail(chemin)
    if erreur:
        return erreur

    try:
        with open(reel, "r", encoding="utf-8") as fichier:
            source = fichier.read()

        try:
            ast.parse(source, filename=reel)
            compile(source, reel, "exec")
            return "SUCCES : aucune erreur de syntaxe à réparer."
        except SyntaxError as exc:
            if exc.msg != "expected ':'" or not exc.lineno:
                return (
                    f"Réparation impossible : {exc.msg}, "
                    f"ligne {exc.lineno}."
                )
            numero_ligne = exc.lineno

        lignes = source.splitlines(keepends=True)
        index = numero_ligne - 1

        if index < 0 or index >= len(lignes):
            return "Erreur : ligne fautive introuvable."

        ligne = lignes[index]
        contenu = ligne.rstrip("\r\n")
        fin = ligne[len(contenu):]

        motif = (
            r"^\s*(?:async\s+def|def|class|if|elif|else|for|while|"
            r"try|except|finally|with|async\s+with|match|case)\b.*\S$"
        )

        if "#" in contenu or not re.match(motif, contenu):
            return "Réparation refusée : ligne non reconnue avec certitude."

        lignes[index] = contenu + ":" + fin
        corrige = "".join(lignes)

        ast.parse(corrige, filename=reel)
        compile(corrige, reel, "exec")

        resultat = ecrire_fichier(relatif, corrige)
        return "Réparation syntaxique vérifiée. " + resultat

    except SyntaxError as exc:
        return f"Réparation refusée : {exc.msg}, ligne {exc.lineno}."
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Erreur pendant la réparation : {exc}"


def executer_tests_python():
    """Execute toute la suite de tests pytest du depot."""
    import subprocess
    import sys

    dossier_tests = os.path.join(DOSSIER_AUTORISE, "tests")
    if not os.path.isdir(dossier_tests):
        return "Erreur : le dossier tests est introuvable."

    commande = [sys.executable, "-m", "pytest", "tests/", "-q"]

    try:
        resultat = subprocess.run(
            commande,
            cwd=DOSSIER_AUTORISE,
            capture_output=True,
            text=True,
            check=False
        )
    except subprocess.TimeoutExpired:
        return "Erreur : délai maximal de 90 secondes dépassé pendant l'exécution des tests pytest."
    except OSError as exc:
        return f"Erreur lors du lancement de pytest : {exc}"

    sortie = ((resultat.stdout or "") + "\n" + (resultat.stderr or "")).strip()
    sortie = sortie[-12000:]

    if resultat.returncode == 0:
        return "SUCCÈS : tous les tests pytest ont réussi.\n" + sortie

    return (
        f"ÉCHEC : pytest a retourné le code {resultat.returncode}.\n"
        + sortie
    )

def executer_programme_python(chemin):
    """Lance un programme Python depuis l'espace de travail."""
    from core.execution_python import executer_programme_python as executer
    return executer(chemin)
