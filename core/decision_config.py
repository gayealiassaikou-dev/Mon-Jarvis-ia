"""Descriptions des outils et agents pour DecisionEngine."""

DESCRIPTIONS_OUTILS = {
    "reparer_syntaxe_python": "Repare localement certaines erreurs de syntaxe Python simples sans IA externe.",
    "analyser_erreur_python": "Analyse un traceback Python et explique la cause probable de l erreur.",
    "diagnostiquer_code_python": "Analyse localement la syntaxe Python et localise les erreurs sans IA externe.",
    "corriger_code_python": "Applique une correction ciblee au code Python apres verification syntaxique.",
    "executer_tests_python": "Lance la suite complete des tests Python du depot et rapporte les erreurs reelles pour aider au debogage.",
"executer_programme_python": "Execute un programme Python de espace_travail pour le developper et le tester.",
    "lire_fichier": (
        "Lit le contenu d'un fichier local du projet."
    ),
    "ecrire_fichier": (
        "Crée ou modifie un fichier local du projet."
    ),
    "supprimer_fichier": (
        "Supprime un fichier local du projet."
    ),
    "supprimer_dossier": (
        "Supprime un dossier local du projet, selon les protections applicables."
    ),
    "lister_fichiers": (
        "Liste les fichiers disponibles dans le projet."
    ),
    "creer_dossier": (
        "Crée un dossier local dans le projet."
    ),
    "rechercher_web": (
        "Effectue une recherche sur le Web pour obtenir des informations externes."
    ),
    "creer_projet": (
        "Crée un projet dans le système de gestion de projets de Jarvis."
    ),
    "ajouter_tache": (
        "Ajoute une tâche à un projet."
    ),
    "lister_projets": (
        "Liste les projets existants."
    ),
    "lister_taches": (
        "Liste les tâches existantes."
    ),
    "terminer_tache": (
        "Marque une tâche comme terminée."
    ),
    "supprimer_tache": (
        "Supprime une tâche."
    ),
    "supprimer_projet": (
        "Supprime un projet."
    ),
    "modifier_statut_projet": (
        "Modifie le statut d'un projet."
    ),
    "github_lister_repos": (
        "Liste les dépôts GitHub accessibles avec l'authentification locale."
    ),
    "github_lire_fichier": (
        "Lit un fichier présent dans un dépôt GitHub."
    ),
    "github_ecrire_fichier": (
        "Crée ou modifie un fichier dans un dépôt GitHub."
    ),
    "github_creer_repo": (
        "Crée un nouveau dépôt GitHub avec l'authentification locale "
        "GitHub CLI, puis vérifie que le dépôt existe."
    ),
    "obtenir_projet_actif": (
        "Identifie le projet actuellement actif dans l'espace de travail."
    ),
    "memoriser_info": (
        "Enregistre une information dans la mémoire de Jarvis."
    ),
    "rechercher_souvenir": (
        "Recherche une information précédemment enregistrée dans la mémoire."
    ),
}


DESCRIPTIONS_AGENTS = {
    "00_directeur_ia": "Coordonne missions complexes, decompose objectifs, orchestre agents.",
    "01_developpeur": "Code, fichiers, GitHub, applications, corrections techniques.",
    "02_designer": "UI, UX, maquettes, identite visuelle.",
    "03_recherche": "Recherches web, comparaisons, verification de sources.",
    "04_business": "Marche, concurrence, monétisation, marketing, modeles economiques.",
    "05_architecte_ia": "Architecture logicielle et IA, composants, technologies.",
    "06_memoire_ia": "Memorisation, organisation, recuperation d'informations.",
    "07_automatisation_ia": "Automatisations, workflows, integrations, taches repetitives.",
    "08_testeur_ia": "Tests logiciels, detection de bugs, qualite et stabilite.",
    "09_securite_ia": "Risques, permissions, secrets, dependances, securite.",
    "10_assistant_vocal_ia": "Voix et controle Android : batterie, volume, luminosite, wifi, notifications, presse-papiers.",
    "11_gestionnaire_outils_ia": "Gere et selectionne les outils disponibles selon la demande.",
}
