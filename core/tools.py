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

# Outils Python deplaces dans core/tools_python.py
from core.tools_python import (  # noqa: F401
    analyser_erreur_python, diagnostiquer_code_python,
    _cible_python_espace_travail, corriger_code_python,
    reparer_syntaxe_python, executer_tests_python,
    executer_programme_python,
)
