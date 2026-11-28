"""Outils projets et taches."""
import os
import json

from core import chemins

DOSSIER_AUTORISE = str(chemins.RACINE_PROJET)

CHEMIN_DONNEES = chemins.chemin_projets_taches()
CHEMIN_PROJET_ACTIF = chemins.chemin_projet_actif()

def _charger_donnees():
    if not os.path.exists(CHEMIN_DONNEES):
        return {"projets": [], "taches": []}
    try:
        with open(CHEMIN_DONNEES, "r", encoding="utf-8") as f:
            donnees = json.load(f)
            donnees.setdefault("projets", [])
            donnees.setdefault("taches", [])
            return donnees
    except (json.JSONDecodeError, ValueError):
        return {"projets": [], "taches": []}

def _sauvegarder_donnees(donnees):
    os.makedirs(os.path.dirname(CHEMIN_DONNEES), exist_ok=True)
    with open(CHEMIN_DONNEES, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=4, ensure_ascii=False)


def lire_etat_projets_taches():
    """Retourne l'etat structure des projets et des taches."""
    return _charger_donnees()

def creer_projet(nom):
    donnees = _charger_donnees()
    for p in donnees["projets"]:
        if p["nom"].strip().lower() == nom.strip().lower():
            return f"Erreur : le projet '{nom}' existe deja."
    donnees["projets"].append({"nom": nom, "statut": "en cours"})
    _sauvegarder_donnees(donnees)
    return f"Projet '{nom}' cree avec succes."

def ajouter_tache(nom, projet=""):
    donnees = _charger_donnees()
    for t in donnees["taches"]:
        if t["nom"].strip().lower() == nom.strip().lower() and t["projet"].strip().lower() == projet.strip().lower():
            return f"Erreur : la tache '{nom}' existe deja pour ce projet."
    donnees["taches"].append({"nom": nom, "projet": projet, "statut": "en attente"})
    _sauvegarder_donnees(donnees)
    return f"Tache '{nom}' ajoutee avec succes."

def lister_projets():
    donnees = _charger_donnees()
    if not donnees["projets"]:
        return "Aucun projet enregistre."
    texte = ""
    for p in donnees["projets"]:
        texte += f"- {p['nom']} ({p['statut']})\n"
    return texte

def definir_projet_actif(nom):
    """Selectionne un projet existant et memorise son nom."""
    if not isinstance(nom, str) or not nom.strip():
        return "Erreur : nom de projet invalide."

    donnees = _charger_donnees()
    for projet in donnees.get("projets", []):
        if not isinstance(projet, dict):
            continue
        nom_projet = projet.get("nom", "")
        if isinstance(nom_projet, str) and nom_projet.strip().lower() == nom.strip().lower():
            os.makedirs(os.path.dirname(CHEMIN_PROJET_ACTIF), exist_ok=True)
            with open(CHEMIN_PROJET_ACTIF, "w", encoding="utf-8") as f:
                json.dump({"nom": nom_projet.strip()}, f, ensure_ascii=False, indent=4)
            return f"Projet actif selectionne : {nom_projet.strip()}."

    return f"Erreur : le projet '{nom.strip()}' n'existe pas."


def _obtenir_nom_projet_actif():
    """Retourne le nom exact du projet actif, ou None si invalide."""
    try:
        with open(CHEMIN_PROJET_ACTIF, "r", encoding="utf-8") as f:
            actif = json.load(f)
        nom = actif.get("nom", "")
        if not isinstance(nom, str) or not nom.strip():
            return None

        for projet in _charger_donnees().get("projets", []):
            if isinstance(projet, dict):
                nom_projet = projet.get("nom", "")
                if isinstance(nom_projet, str) and nom_projet.strip().lower() == nom.strip().lower():
                    return nom_projet.strip()
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return None


def obtenir_projet_actif():
    """Retrouve le projet actif memorise et verifie qu'il existe encore."""
    if not os.path.exists(CHEMIN_PROJET_ACTIF):
        return "Aucun projet actif selectionne."

    try:
        with open(CHEMIN_PROJET_ACTIF, "r", encoding="utf-8") as f:
            donnees_actives = json.load(f)
        nom = donnees_actives.get("nom", "")
        if not isinstance(nom, str) or not nom.strip():
            return "Erreur : fichier du projet actif invalide."

        for projet in _charger_donnees().get("projets", []):
            if isinstance(projet, dict):
                nom_projet = projet.get("nom", "")
                if isinstance(nom_projet, str) and nom_projet.strip().lower() == nom.strip().lower():
                    return f"Projet actif : {nom_projet.strip()}."

        return f"Le projet memorise '{nom}' n'existe plus dans la liste des projets."
    except (OSError, json.JSONDecodeError, AttributeError):
        return "Erreur : impossible de lire le projet actif."


def lister_taches():
    donnees = _charger_donnees()
    if not donnees["taches"]:
        return "Aucune tache enregistree."
    texte = ""
    for t in donnees["taches"]:
        texte += f"- {t['nom']} [{t['statut']}]"
        if t["projet"]:
            texte += f" (projet: {t['projet']})"
        texte += "\n"
    return texte

# Outils GitHub deplaces dans core/tools_github.py
from core.tools_github import (  # noqa: F401
    _headers_github, _interpreter_erreur_github,
    github_creer_repo_original_en_ligne, github_creer_repo,
    github_lister_repos_original_en_ligne, github_lister_repos,
    _github_resoudre_repo, _github_entetes, _github_message_erreur,
    github_lire_fichier_original_en_ligne, github_lire_fichier,
    github_ecrire_fichier_original_en_ligne, github_ecrire_fichier,
)

def terminer_tache(nom):
    donnees = _charger_donnees()
    for t in donnees["taches"]:
        if t["nom"] == nom:
            t["statut"] = "terminee"
            _sauvegarder_donnees(donnees)
            return f"Tache '{nom}' marquee comme terminee."
    return f"Erreur : tache '{nom}' introuvable."

def supprimer_tache(nom):
    donnees = _charger_donnees()
    taille_avant = len(donnees["taches"])
    donnees["taches"] = [t for t in donnees["taches"] if t["nom"] != nom]
    if len(donnees["taches"]) == taille_avant:
        return f"Erreur : tache '{nom}' introuvable."
    _sauvegarder_donnees(donnees)
    return f"Tache '{nom}' supprimee avec succes."

def supprimer_projet(nom):
    import unicodedata
    from difflib import SequenceMatcher

    donnees = _charger_donnees()

    def normaliser_nom(valeur):
        texte = unicodedata.normalize("NFKD", str(valeur or "").strip().casefold())
        texte = "".join(c for c in texte if not unicodedata.combining(c))
        return " ".join(texte.split())

    nom_recherche = normaliser_nom(nom)
    projets_avant = donnees["projets"]

    correspondances = [
        p for p in projets_avant
        if isinstance(p, dict)
        and normaliser_nom(p.get("nom", "")) == nom_recherche
    ]

    if not correspondances:
        ressemblances = [
            str(p.get("nom", "")).strip()
            for p in projets_avant
            if isinstance(p, dict)
            and isinstance(p.get("nom"), str)
            and SequenceMatcher(
                None, nom_recherche, normaliser_nom(p["nom"])
            ).ratio() >= 0.70
        ]
        if ressemblances:
            return (
                f"Confirmation requise : le nom '{nom}' ne correspond pas exactement. "
                f"Projet ressemblant trouvé : {', '.join(ressemblances)}. "
                "Aucun projet n'a été supprimé. Confirme le nom exact."
            )
        return f"Erreur : projet '{nom}' introuvable."

    if len(correspondances) > 1:
        return (
            f"Erreur : plusieurs projets correspondent à '{nom}'. "
            "Aucun projet n'a été supprimé."
        )

    projet_cible = correspondances[0]
    donnees["projets"] = [
        p for p in projets_avant if p is not projet_cible
    ]
    _sauvegarder_donnees(donnees)
    return f"Projet '{projet_cible.get('nom', nom)}' supprime avec succes."

def modifier_statut_projet(nom, nouveau_statut):
    statuts_valides = ["en cours", "en pause", "termine", "annule"]
    if nouveau_statut.strip().lower() not in statuts_valides:
        return f"Erreur : statut invalide. Statuts valides : {', '.join(statuts_valides)}."
    donnees = _charger_donnees()
    for p in donnees["projets"]:
        if p["nom"].strip().lower() == nom.strip().lower():
            p["statut"] = nouveau_statut.strip().lower()
            _sauvegarder_donnees(donnees)
            return f"Projet '{nom}' passe au statut '{nouveau_statut}'."
    return f"Erreur : projet '{nom}' introuvable."



