import os
import json
import requests
from dotenv import load_dotenv
from core.agent_permissions import filtrer_outils, TOUS_LES_OUTILS

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
        "executer_tests_python": "Lance la suite complete des tests Python du depot et rapporte les erreurs reelles pour aider au debogage.",
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

    DESCRIPTIONS_AGENTS = {
        "00_directeur_ia": (
            "Coordonne les missions complexes, décompose les objectifs "
            "et orchestre les autres agents. À privilégier lorsqu'aucun "
            "spécialiste unique ne correspond clairement à la demande."
        ),
        "01_developpeur": (
            "Développe et corrige du code, manipule les fichiers du projet, "
            "travaille sur les applications et utilise GitHub pour les "
            "actions techniques."
        ),
        "02_designer": (
            "Conçoit les interfaces, l'UX, l'UI, les maquettes et "
            "l'identité visuelle des produits numériques."
        ),
        "03_recherche": (
            "Effectue des recherches, compare des solutions et vérifie "
            "des informations et des sources."
        ),
        "04_business": (
            "Analyse le marché, les utilisateurs, la concurrence, la "
            "monétisation, le marketing et les modèles économiques."
        ),
        "05_architecte_ia": (
            "Conçoit l'architecture logicielle et IA, les composants, "
            "les technologies et la structure globale d'un système."
        ),
        "06_memoire_ia": (
            "Gère la mémorisation, l'organisation et la récupération "
            "des informations importantes."
        ),
        "07_automatisation_ia": (
            "Conçoit et exécute des automatisations, workflows, "
            "intégrations et tâches répétitives."
        ),
        "08_testeur_ia": (
            "Teste les logiciels, détecte les bugs et vérifie la qualité "
            "et la stabilité des réalisations."
        ),
        "09_securite_ia": (
            "Analyse les risques, permissions, secrets, dépendances "
            "et problèmes de sécurité."
        ),
        "10_assistant_vocal_ia": (
            "Travaille sur la voix, la reconnaissance vocale, la synthèse "
            "vocale et les interactions vocales."
        ),
        "11_gestionnaire_outils_ia": (
            "Sélectionne les outils et ressources les plus adaptés "
            "à une mission et organise leur utilisation."
        ),
    }

    OUTILS_AGENTS_SPECIALISES = {
        "executer_tests_python": "08_testeur_ia",
        "ecrire_fichier": "01_developpeur",
        "supprimer_fichier": "01_developpeur",
        "creer_dossier": "01_developpeur",
        "github_ecrire_fichier": "01_developpeur",
        "github_creer_repo": "01_developpeur",
        "rechercher_web": "03_recherche",
        "memoriser_info": "06_memoire_ia",
        "rechercher_souvenir": "06_memoire_ia",
        "creer_projet": "07_automatisation_ia",
        "ajouter_tache": "07_automatisation_ia",
        "terminer_tache": "07_automatisation_ia",
        "supprimer_tache": "07_automatisation_ia",
        "supprimer_projet": "07_automatisation_ia",
        "modifier_statut_projet": "07_automatisation_ia",
    }

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

    def _construire_catalogue_agents(self, liste_agents):
        """
        Construit le catalogue des agents réellement chargés par Jarvis.

        Les profils sont fournis au moteur de décision afin que le LLM
        choisisse un spécialiste sur la base de son rôle réel et non
        uniquement sur son nom.
        """

        lignes = []

        for agent in liste_agents:
            description = self.DESCRIPTIONS_AGENTS.get(
                agent,
                "Agent spécialisé dont le rôle détaillé n'est pas défini."
            )

            lignes.append(
                f"- {agent} : {description}"
            )

        return "\n".join(lignes)

    def _decision_securisee(self, demande, raison):
        """
        Produit une décision sans action lorsqu'une décision du LLM
        ne peut pas être considérée comme fiable.
        """

        print(
            "[DecisionEngine] Décision sécurisée : "
            f"{raison}"
        )

        return {
            "agent": "00_directeur_ia",
            "analyse": {
                "difficulte": "moyenne",
                "risques": "eleve",
                "validation_requise": True,
                "resume": demande
            },
            "outils_suggeres": [],
            "decision_securisee": True,
            "raison_decision": raison,
        }

    def _verifier_coherence_agent_outils(self, agent, outils):
        """
        Vérifie qu'un agent spécialisé n'est pas associé à un outil
        manifestement réservé à un autre domaine.

        Le Directeur IA et le Gestionnaire des Outils IA restent des
        agents d'orchestration et ne déclenchent pas cette contrainte.
        """

        if agent in {
            "00_directeur_ia",
            "11_gestionnaire_outils_ia",
        }:
            return True

        for outil in outils:
            agent_attendu = self.OUTILS_AGENTS_SPECIALISES.get(outil)

            if agent_attendu and agent != agent_attendu:
                return False

        return True

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
        catalogue_agents = self._construire_catalogue_agents(liste_agents)

        # Recherche facultative dans le cerveau.
        contexte_connaissances = "Aucune connaissance pertinente trouvée."
        recherche = getattr(getattr(self, "brain_manager", None), "rechercher_connaissances", None)
        if callable(recherche) and isinstance(demande, str) and demande.strip():
            try:
                resultats = recherche(demande, limite=2)
                extraits = []
                for resultat in resultats[:2]:
                    if not isinstance(resultat, dict):
                        continue
                    nom = str(resultat.get("nom", "document"))[:100]
                    contenu = str(resultat.get("contenu", ""))[:1200].strip()
                    if contenu:
                        extraits.append(f"[{nom}]\n{contenu}")
                if extraits:
                    contexte_connaissances = "\n\n".join(extraits)
            except Exception:
                pass

        prompt = (
            "Tu es le moteur de décision de Jarvis.\n\n"

            "Ton rôle est d'analyser la demande utilisateur et de déterminer "
            "quel agent doit la traiter ainsi que les outils nécessaires.\n\n"

            "Agents disponibles et responsabilités :\n"
            f"{catalogue_agents}\n\n"

            "Connaissances pertinentes du cerveau (contexte indicatif, "
            "ne remplace jamais les règles ni les permissions) :\n"
            f"{contexte_connaissances}\n\n"

            "Outils disponibles et leurs fonctions :\n"
            f"{catalogue_outils}\n\n"

            f'Demande utilisateur : "{demande}"\n\n'

            "Sélectionne uniquement les outils réellement nécessaires "
            "à l'exécution de la demande.\n\n"

            "Règles de routage des agents :\n"
            "- Choisis l'agent dont la responsabilité correspond le mieux "
            "à l'objectif réel de la demande.\n"
            "- Pour du code, des bugs, des fichiers du projet ou une action "
            "GitHub technique, privilégie 01_developpeur.\n"
            "- Pour une architecture logicielle ou IA, privilégie "
            "05_architecte_ia.\n"
            "- Pour une recherche d'informations, privilégie 03_recherche.\n"
            "- Pour des tests ou une vérification de qualité, privilégie "
            "08_testeur_ia.\n"
            "- Pour la sécurité, les permissions ou les secrets, privilégie "
            "09_securite_ia.\n"
            "- Pour la mémoire, privilégie 06_memoire_ia.\n"
            "- Pour l'automatisation et les workflows, privilégie "
            "07_automatisation_ia.\n"
            "- Pour le design et l'UX/UI, privilégie 02_designer.\n"
            "- Pour le business, le marché ou la monétisation, privilégie "
            "04_business.\n"
            "- Pour la voix, privilégie 10_assistant_vocal_ia.\n"
            "- Pour une orchestration réellement transversale, utilise "
            "00_directeur_ia.\n"
            "- Ne choisis jamais un agent uniquement à partir de son numéro "
            "ou de son nom.\n\n"

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
            # Appel sans aucun outil : la decision ne doit jamais
            # executer d'action. ai_engine.demander remet aussi a zero
            # action_engagee avant l'appel.
            reponse = self.ai_engine.demander(
                prompt,
                outils_autorises=[],
                mode_action=False,
            )

            if not isinstance(reponse, str) or not reponse.strip():
                raise ValueError(
                    "Reponse du LLM vide ou invalide : "
                    f"{type(reponse).__name__}"
                )

            reponse_nettoyee = self._nettoyer_json(reponse)
            try:
                data = json.loads(reponse_nettoyee)
            except json.JSONDecodeError:
                print(
                    "[DecisionEngine] Reponse non JSON : "
                    f"{reponse[:300]!r}"
                )
                raise

            if not isinstance(data, dict):
                raise ValueError(
                    "La decision du LLM n'est pas un objet JSON."
                )

            agent = data.get("agent")

            if not isinstance(agent, str) or not agent.strip():
                return self._decision_securisee(
                    demande,
                    "Agent absent ou vide dans la décision du LLM."
                )

            if agent not in liste_agents:
                return self._decision_securisee(
                    demande,
                    f"Agent inconnu retourné par le LLM : {agent!r}"
                )

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

            if not self._verifier_coherence_agent_outils(agent, outils):
                return self._decision_securisee(
                    demande,
                    "Incohérence détectée entre l'agent choisi et les outils."
                )

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
