"""Outils fichiers et dossiers."""
import unicodedata
import os
import difflib
import re
import json
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

