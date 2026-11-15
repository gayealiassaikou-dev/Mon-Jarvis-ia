import os
import json
import requests
from dotenv import load_dotenv
from core.agent_permissions import filtrer_outils, TOUS_LES_OUTILS

load_dotenv()


from core.decision_config import DESCRIPTIONS_OUTILS, DESCRIPTIONS_AGENTS
from core.decision_local import DecisionLocalMixin
from core.decision_core import DecisionCoreMixin


class DecisionEngine(DecisionCoreMixin, DecisionLocalMixin):
    # Alias pour compatibilite : les descriptions vivent dans decision_config.py
    DESCRIPTIONS_OUTILS = DESCRIPTIONS_OUTILS
    DESCRIPTIONS_AGENTS = DESCRIPTIONS_AGENTS

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


    def __init__(self, brain_manager, agent_manager, ai_engine):
        self.brain_manager = brain_manager
        self.agent_manager = agent_manager
        self.ai_engine = ai_engine

        self.providers = [
            {"nom": "groq", "url": "https://api.groq.com/openai/v1/chat/completions", "model": "openai/gpt-oss-120b", "api_key_env": "GROQ_API_KEY", "type": "openai_compatible"},
            {"nom": "mistral", "url": "https://api.mistral.ai/v1/chat/completions", "model": "mistral-small-latest", "api_key_env": "MISTRAL_API_KEY", "type": "openai_compatible"},
            {"nom": "gemini", "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent", "model": "gemini-flash-lite-latest", "api_key_env": "GEMINI_API_KEY", "type": "gemini"},
        ]

        from core.agent_permissions import TOUS_LES_OUTILS
        self.outils_disponibles = list(TOUS_LES_OUTILS)

    def _appeler_llm(self, prompt, timeout=8):
        erreurs = []
        for provider in self.providers:
            api_key = os.getenv(provider["api_key_env"])
            if not api_key:
                continue
            try:
                if provider["type"] == "gemini":
                    url = f"{provider['url']}?key={api_key}"
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    r = requests.post(url, json=payload, timeout=(3, timeout))
                    r.raise_for_status()
                    data = r.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                else:
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    payload = {"model": provider["model"], "messages": [{"role": "user", "content": prompt}]}
                    r = requests.post(provider["url"], headers=headers, json=payload, timeout=(3, timeout))
                    r.raise_for_status()
                    data = r.json()
                    return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                erreurs.append(f"{provider['nom']}: {type(e).__name__} {str(e)[:80]}")
                continue
        raise RuntimeError("DecisionEngine: aucun provider n a repondu. " + " | ".join(erreurs))

    def _nettoyer_json(self, texte):
        texte = texte.strip()

        if texte.startswith("```"):
            texte = texte.strip("`")

            if texte.startswith("json"):
                texte = texte[4:]

        return texte.strip()


    OUTILS_AGENTS_SPECIALISES = {
        "reparer_syntaxe_python": "01_developpeur",
        "analyser_erreur_python": "01_developpeur",
        "diagnostiquer_code_python": "01_developpeur",
        "corriger_code_python": "01_developpeur",
        "executer_tests_python": "08_testeur_ia",
    "executer_programme_python": "01_developpeur",
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
        "lire_batterie": "10_assistant_vocal_ia",
        "regler_volume": "10_assistant_vocal_ia",
        "lampe_torche": "10_assistant_vocal_ia",
        "envoyer_notification": "10_assistant_vocal_ia",
        "lire_presse_papiers": "10_assistant_vocal_ia",
        "regler_luminosite": "10_assistant_vocal_ia",
        "lire_wifi": "10_assistant_vocal_ia",
        "lire_notifications": "10_assistant_vocal_ia",
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
            "complexite": "simple",
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
                if agent == "08_testeur_ia" and outil == "executer_programme_python":
                    continue
                return False

        return True

    def choisir_agent(self, demande):
        return self.decider(demande)["agent"]

    def obtenir_contexte_agent(self, nom_agent):
        return self.agent_manager.agents.get(nom_agent, "")
