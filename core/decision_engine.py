import os
import json
import requests
from dotenv import load_dotenv
from agent_permissions import filtrer_outils, TOUS_LES_OUTILS

load_dotenv()


class DecisionEngine:
    """
    Moteur de décision de Jarvis.

    Son rôle est de :
    - choisir l'agent adapté ;
    - identifier les outils nécessaires ;
    - déterminer le niveau de risque ;
    - appliquer les permissions de l'agent.

    Le DecisionEngine ne possède aucun droit supplémentaire :
    les permissions restent la barrière de sécurité finale.
    """

    DESCRIPTIONS_OUTILS = {
        "lire_fichier": (
            "Lit le contenu d'un fichier local du projet."
        ),
        "ecrire_fichier": (
            "Crée ou modifie un fichier local du projet."
        ),
        "supprimer_fichier": (
            "Supprime un fichier local du projet."
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
        "memoriser_info": (
            "Enregistre une information dans la mémoire de Jarvis."
        ),
        "rechercher_souvenir": (
            "Recherche une information précédemment enregistrée dans la mémoire."
        ),
    }

    def __init__(self, brain_manager, agent_manager, ai_engine):
        self.brain_manager = brain_manager
        self.agent_manager = agent_manager
        self.ai_engine = ai_engine
        self.api_key = os.getenv("GROQ_API_KEY")
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"

        # Source unique de vérité pour le catalogue des outils.
        # Les permissions de chaque agent sont appliquées ensuite
        # par filtrer_outils().
        self.outils_disponibles = list(TOUS_LES_OUTILS)

    def _appeler_llm(self, prompt, timeout=15):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        reponse = requests.post(
            self.url,
            headers=headers,
            json=payload,
            timeout=timeout
        )

        reponse.raise_for_status()

        data = reponse.json()
        return data["choices"][0]["message"]["content"].strip()

    def _nettoyer_json(self, texte):
        texte = texte.strip()

        if texte.startswith("```"):
            texte = texte.strip("`")

            if texte.startswith("json"):
                texte = texte[4:]

        return texte.strip()

    def _construire_catalogue_outils(self):
        """
        Construit la description sémantique des outils disponibles.

        Seuls les outils présents dans TOUS_LES_OUTILS sont exposés.
        """

        lignes = []

        for outil in self.outils_disponibles:
            description = self.DESCRIPTIONS_OUTILS.get(
                outil,
                "Outil disponible dans le système de Jarvis."
            )

            lignes.append(
                f"- {outil} : {description}"
            )

        return "\n".join(lignes)

    def decider(self, demande):
        liste_agents = list(self.agent_manager.agents.keys())

        defaut = {
            "agent": "00_directeur_ia",
            "analyse": {
                "difficulte": "moyenne",
                "risques": "faible",
                "validation_requise": False,
                "resume": demande
            },
            "outils_suggeres": []
        }

        catalogue_outils = self._construire_catalogue_outils()

        prompt = (
            "Tu es le moteur de décision de Jarvis.\n\n"

            "Ton rôle est d'analyser la demande utilisateur et de déterminer "
            "quel agent doit la traiter ainsi que les outils nécessaires.\n\n"

            f"Agents disponibles : {', '.join(liste_agents)}.\n\n"

            "Outils disponibles et leurs fonctions :\n"
            f"{catalogue_outils}\n\n"

            f'Demande utilisateur : "{demande}"\n\n'

            "Sélectionne uniquement les outils réellement nécessaires "
            "à l'exécution de la demande.\n\n"

            "Règles importantes pour les outils :\n"
            "- Pour créer un dépôt GitHub, utilise github_creer_repo.\n"
            "- Pour lister des dépôts GitHub, utilise github_lister_repos.\n"
            "- Pour lire un fichier GitHub, utilise github_lire_fichier.\n"
            "- Pour créer ou modifier un fichier GitHub, utilise github_ecrire_fichier.\n"
            "- Ne sélectionne pas un outil uniquement parce que son nom semble proche "
            "de la demande.\n"
            "- Si aucun outil n'est nécessaire, retourne une liste vide.\n"
            "- Ne retourne jamais un outil qui n'existe pas dans la liste fournie.\n\n"

            "Réponds UNIQUEMENT avec un objet JSON valide, "
            "sans texte avant ou après, exactement au format suivant :\n"

            '{"agent": "nom exact d’un agent de la liste", '
            '"difficulte": "faible|moyenne|elevee", '
            '"risques": "aucun|faible|moyen|eleve", '
            '"validation_requise": true ou false, '
            '"resume": "resume court de l’objectif en une phrase", '
            '"outils_suggeres": ["liste des outils nécessaires"]}\n\n'

            "validation_requise doit être true uniquement si la demande "
            "modifie, supprime, crée des fichiers, installe, déploie ou "
            "exécute une action irréversible.\n"

            "Pour une analyse, une explication, une idée, une planification "
            "ou une proposition, validation_requise doit toujours être false."
        )

        try:
            reponse = self.ai_engine.router.demander(prompt)

            reponse_nettoyee = self._nettoyer_json(reponse)
            data = json.loads(reponse_nettoyee)

            agent = data.get("agent", "00_directeur_ia")

            if agent not in liste_agents:
                agent = "00_directeur_ia"

            outils = data.get("outils_suggeres", [])

            if not isinstance(outils, list):
                raise ValueError(
                    "Le champ outils_suggeres doit être une liste."
                )

            outils = [
                outil
                for outil in outils
                if outil in self.outils_disponibles
            ]

            # Barrière de sécurité : les outils proposés par le LLM
            # sont toujours filtrés par les permissions de l'agent.
            outils = filtrer_outils(agent, outils)

            return {
                "agent": agent,
                "analyse": {
                    "difficulte": data.get(
                        "difficulte",
                        "moyenne"
                    ),
                    "risques": data.get(
                        "risques",
                        "faible"
                    ),
                    "validation_requise": data.get(
                        "validation_requise",
                        False
                    ),
                    "resume": data.get(
                        "resume",
                        demande
                    )
                },
                "outils_suggeres": outils
            }

        except Exception as erreur:
            print(
                "[DecisionEngine] Erreur de décision : "
                f"{type(erreur).__name__}: {erreur}"
            )

            return defaut

    def choisir_agent(self, demande):
        return self.decider(demande)["agent"]

    def obtenir_contexte_agent(self, nom_agent):
        return self.agent_manager.agents.get(nom_agent, "")
