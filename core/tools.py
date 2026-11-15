import unicodedata
import os
import difflib
import re
import json
import requests
import base64
import shutil

DOSSIER_AUTORISE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _chemin_autorise(chemin_complet):
    chemin_reel = os.path.realpath(chemin_complet)
    dossier_reel = os.path.realpath(DOSSIER_AUTORISE)

    try:
        return os.path.commonpath(
            [chemin_reel, dossier_reel]
        ) == dossier_reel
    except ValueError:
        return False

FICHIERS_PROTEGES = [
    os.path.join(DOSSIER_AUTORISE, ".env"),
    os.path.join(DOSSIER_AUTORISE, ".git"),
]

DOSSIERS_PROTEGES = [
    os.path.join(DOSSIER_AUTORISE, "core"),
    os.path.join(DOSSIER_AUTORISE, ".git"),
]

def _fichier_protege(chemin_complet):
    for proteg in FICHIERS_PROTEGES:
        if chemin_complet == proteg:
            return True
    for dossier in DOSSIERS_PROTEGES:
        try:
            if os.path.commonpath([chemin_complet, dossier]) == dossier:
                return True
        except ValueError:
            continue
    return False


def _normaliser_nom_chemin(valeur):
    texte = unicodedata.normalize("NFKD", str(valeur))
    texte = texte.encode("ascii", "ignore").decode("ascii").lower()
    texte = texte.replace("\\", "/")
    mots = []
    for partie in texte.split("/"):
        partie = re.sub(r"^\d+[\s._-]*", "", partie)
        partie = re.sub(r"[_\-.]+", " ", partie)
        mots.extend(re.findall(r"[a-z0-9]+", partie))
    stop = {"de", "du", "des", "la", "le", "les", "un", "une", "d", "l", "a", "au", "aux", "et"}
    return " ".join(m for m in mots if m not in stop)


def _chercher_dossiers_similaires(dossier, limite=5):
    """Recherche des chemins proches, fichiers compris, dans le projet autorisé."""
    cible = _normaliser_nom_chemin(dossier)
    if not cible:
        return []

    exclusions = {
        ".git", ".patches", ".venv", "venv", "env", "node_modules",
        "__pycache__", ".pytest_cache"
    }
    resultats = []

    for racine, sous_dossiers, fichiers in os.walk(
        DOSSIER_AUTORISE, topdown=True, followlinks=False
    ):
        sous_dossiers[:] = [
            nom for nom in sous_dossiers
            if nom not in exclusions
            and _chemin_autorise(os.path.realpath(os.path.join(racine, nom)))
            and not _fichier_protege(os.path.realpath(os.path.join(racine, nom)))
        ]

        for nom in sous_dossiers + fichiers:
            chemin = os.path.join(racine, nom)
            reel = os.path.realpath(chemin)
            if not _chemin_autorise(reel) or _fichier_protege(reel):
                continue

            relatif = os.path.relpath(chemin, DOSSIER_AUTORISE)
            base = os.path.splitext(nom)[0] if os.path.isfile(chemin) else nom
            nom_normalise = _normaliser_nom_chemin(base)
            chemin_normalise = _normaliser_nom_chemin(
                os.path.splitext(relatif)[0] if os.path.isfile(chemin) else relatif
            )

            candidats = [x for x in (nom_normalise, chemin_normalise) if x]
            if not candidats:
                continue

            score = max(
                difflib.SequenceMatcher(None, cible, candidat).ratio()
                for candidat in candidats
            )

            mots_cible = cible.split()
            mots_nom = nom_normalise.split()
            if mots_cible and mots_nom:
                correspondance = sum(
                    1.0 if mot in mots_nom else max(
                        difflib.SequenceMatcher(None, mot, autre).ratio()
                        for autre in mots_nom
                    )
                    for mot in mots_cible
                ) / len(mots_cible)
                score = max(score, correspondance)

            if score >= 0.50:
                resultats.append((score, relatif))

    resultats.sort(key=lambda item: (-item[0], item[1].lower()))
    return [chemin for _, chemin in resultats[:limite]]

def creer_parent_manquant_pour_ecriture(chemin):
    """Cree un seul dossier parent manquant dans le projet autorise."""
    if not isinstance(chemin, str) or not chemin:
        return False

    chemin_complet = os.path.abspath(
        os.path.join(DOSSIER_AUTORISE, chemin)
    )
    if not _chemin_autorise(chemin_complet):
        return False

    chemin_reel = os.path.realpath(chemin_complet)
    if not _chemin_autorise(chemin_reel):
        return False
    if _fichier_protege(chemin_reel):
        return False
    if os.path.exists(chemin_reel):
        return False

    parent = os.path.dirname(chemin_reel)
    if os.path.isdir(parent) or not _chemin_autorise(parent):
        return False

    parent_reel = os.path.realpath(parent)
    if not _chemin_autorise(parent_reel):
        return False
    if _fichier_protege(parent_reel):
        return False

    parent_du_parent = os.path.dirname(parent_reel)
    if not os.path.isdir(parent_du_parent):
        return False
    if not _chemin_autorise(parent_du_parent):
        return False

    try:
        os.mkdir(parent_reel)
        return True
    except OSError:
        return False


def lire_fichier(chemin):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : accès refusé, fichier ou dossier protégé."

    if not os.path.exists(chemin_reel):
        return f"Erreur : le fichier {chemin} n'existe pas."

    with open(chemin_reel, "r", encoding="utf-8") as f:
        return f.read()

def ecrire_fichier(chemin, contenu):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)
    if not _chemin_autorise(chemin_reel):
        return "Erreur : accès refusé en dehors du projet."

    if _fichier_protege(chemin_reel):
        return f"Erreur : {chemin} est un fichier protege, modification refusee."

    dossier_parent = os.path.dirname(chemin_reel)
    if not os.path.isdir(dossier_parent):
        return f"Erreur : le dossier parent de {chemin} n'existe pas. Creez d'abord le dossier cible."

    if os.path.isdir(chemin_reel):
        return f"Erreur : {chemin} est un dossier, pas un fichier."

    if not isinstance(contenu, str):
        return "Erreur : le contenu du fichier doit être du texte."

    try:
        with open(chemin_reel, "w", encoding="utf-8") as f:
            f.write(contenu)

        with open(chemin_reel, "r", encoding="utf-8") as f:
            if f.read() != contenu:
                return f"Erreur : vérification échouée après écriture de {chemin}."

        return f"Fichier {chemin} écrit et vérifié avec succès."
    except (OSError, UnicodeError) as exc:
        return f"Erreur : impossible d'écrire ou de vérifier {chemin} : {exc}"

def supprimer_fichier(chemin):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))
    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."
    if _fichier_protege(chemin_complet):
        return f"Erreur : {chemin} est un fichier protege, suppression refusee."
    if not os.path.exists(chemin_complet):
        return f"Erreur : le fichier {chemin} n'existe pas, rien a supprimer."
    os.remove(chemin_complet)
    return f"Fichier {chemin} supprime avec succes."



def supprimer_dossier(chemin):
    """Supprime un dossier du projet après validation des protections."""
    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : chemin du dossier absent."

    chemin = chemin.strip()
    chemin_complet = os.path.abspath(
        os.path.join(DOSSIER_AUTORISE, chemin)
    )
    chemin_reel = os.path.realpath(chemin_complet)
    racine_reelle = os.path.realpath(DOSSIER_AUTORISE)

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    if chemin_reel == racine_reelle:
        return "Erreur : la racine du projet ne peut pas être supprimée."

    chemin_relatif = os.path.relpath(chemin_complet, DOSSIER_AUTORISE)
    chemin_verifie = DOSSIER_AUTORISE

    for composant in chemin_relatif.split(os.sep):
        if composant in ("", "."):
            continue
        chemin_verifie = os.path.join(chemin_verifie, composant)
        if os.path.islink(chemin_verifie):
            return "Erreur : les chemins contenant un lien symbolique ne peuvent pas être supprimés."


    if _fichier_protege(chemin_reel):
        return f"Erreur : {chemin} est un chemin protégé."

    if not os.path.exists(chemin_reel):
        return f"Erreur : le dossier {chemin} n'existe pas."

    if not os.path.isdir(chemin_reel):
        return f"Erreur : {chemin} n'est pas un dossier."

    try:
        shutil.rmtree(chemin_reel)
        return f"Dossier {chemin} supprimé avec succès."
    except OSError as exc:
        return f"Erreur : impossible de supprimer le dossier {chemin} : {exc}"

def lister_fichiers_original_en_ligne(dossier="."):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, dossier))

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : accès refusé, dossier protégé."

    if not os.path.exists(chemin_reel):
        suggestions = _chercher_dossiers_similaires(dossier)
        if suggestions:
            liste = "\n".join(f"- {x}" for x in suggestions)
            return (
                f"Aucun dossier exact nommé '{dossier}' n'existe. "
                f"Chemins proches trouvés (fichiers et dossiers) :\n{liste}\n"
                "Vérifie le chemin proposé avant de réessayer. "
                "Aucun fichier ni dossier n'a été ouvert automatiquement."
            )
        return f"Erreur : le dossier {dossier} n'existe pas et aucun dossier proche n'a été trouvé."

    if not os.path.isdir(chemin_reel):
        return f"Erreur : {dossier} n'est pas un dossier."

    elements = os.listdir(chemin_reel)

    if not elements:
        return f"Le dossier {dossier} est vide."

    return "\n".join(sorted(elements))


import functools as _ft
@_ft.wraps(lister_fichiers_original_en_ligne)
def lister_fichiers(*args, **kwargs):
    r = lister_fichiers_original_en_ligne(*args, **kwargs)
    if isinstance(r, str):
        return '[Contenu des fichiers du serveur de Sam Sarr, PAS du depot GitHub]\n' + r
    return r

def creer_dossier(chemin):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : création refusée dans un dossier protégé."

    if os.path.exists(chemin_reel):
        return f"Le dossier {chemin} existe deja."

    os.makedirs(chemin_reel)

    return f"Dossier {chemin} cree avec succes."

# rechercher_web deplace dans core/tools_web.py
from core.tools_web import rechercher_web  # noqa: F401

# Outils GitHub deplaces dans core/tools_github.py
from core.tools_github import (  # noqa: F401
    _headers_github, _interpreter_erreur_github,
    github_creer_repo_original_en_ligne, github_creer_repo,
    github_lister_repos_original_en_ligne, github_lister_repos,
    _github_resoudre_repo, _github_entetes, _github_message_erreur,
    github_lire_fichier_original_en_ligne, github_lire_fichier,
    github_ecrire_fichier_original_en_ligne, github_ecrire_fichier,
)

# Outils projets/taches deplaces dans core/tools_projets.py
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
