TOUS_LES_OUTILS = [
    "lire_fichier", "ecrire_fichier", "supprimer_fichier",
    "lister_fichiers", "creer_dossier",
    "rechercher_web",
    "creer_projet", "ajouter_tache", "lister_projets", "lister_taches",
    "terminer_tache", "supprimer_tache", "supprimer_projet", "modifier_statut_projet",
    "github_lister_repos", "github_lire_fichier", "github_ecrire_fichier",
    "memoriser_info", "rechercher_souvenir"
]

PERMISSIONS_AGENTS = {
    "00_directeur_ia": TOUS_LES_OUTILS,

    "01_developpeur": [
        "lire_fichier", "ecrire_fichier", "supprimer_fichier",
        "lister_fichiers", "creer_dossier",
        "github_lister_repos", "github_lire_fichier", "github_ecrire_fichier"
    ],

    "02_designer": [
        "lire_fichier", "ecrire_fichier", "lister_fichiers"
    ],

    "03_recherche": [
        "rechercher_web", "lire_fichier", "lister_fichiers"
    ],

    "04_business": [
        "rechercher_web", "lister_projets", "lister_taches", "lire_fichier"
    ],

    "05_architecte_ia": [
        "lire_fichier", "lister_fichiers", "creer_dossier",
        "github_lister_repos", "github_lire_fichier"
    ],

    "06_memoire_ia": [
        "lire_fichier", "ecrire_fichier", "lister_fichiers",
        "memoriser_info", "rechercher_souvenir"
    ],

    "07_automatisation_ia": [
        "lire_fichier", "ecrire_fichier", "lister_fichiers", "creer_dossier",
        "github_lister_repos", "github_lire_fichier", "github_ecrire_fichier",
        "creer_projet", "ajouter_tache",
        "terminer_tache", "supprimer_tache", "supprimer_projet", "modifier_statut_projet"
    ],

    "08_testeur_ia": [
        "lire_fichier", "lister_fichiers"
    ],

    "09_securite_ia": [
        "lire_fichier", "lister_fichiers"
    ],

    "10_assistant_vocal_ia": [
        "lister_projets", "lister_taches"
    ],

    "11_gestionnaire_outils_ia": TOUS_LES_OUTILS
}


def obtenir_outils_autorises(nom_agent):
    return PERMISSIONS_AGENTS.get(nom_agent, [])


def filtrer_outils(nom_agent, outils_suggeres):
    autorises = obtenir_outils_autorises(nom_agent)
    return [o for o in outils_suggeres if o in autorises]
