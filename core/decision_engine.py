import os
import json
import requests
from dotenv import load_dotenv
from agent_permissions import filtrer_outils

load_dotenv()


class DecisionEngine:

    def __init__(self, brain_manager, agent_manager, ai_engine):
        self.brain_manager = brain_manager
        self.agent_manager = agent_manager
        self.ai_engine = ai_engine
        self.api_key = os.getenv("GROQ_API_KEY")
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"

        self.outils_disponibles = [
            "lire_fichier",
            "ecrire_fichier",
            "supprimer_fichier",
            "rechercher_web",
            "creer_projet",
            "ajouter_tache",
            "lister_projets",
            "lister_taches"
        ]

    def _appeler_llm(self, prompt, timeout=15):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        reponse = requests.post(self.url, headers=headers, json=payload, timeout=timeout)
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

        prompt = (
            f"Tu es le moteur de decision de Jarvis, un assistant IA.\n\n"
            f"Agents disponibles : {', '.join(liste_agents)}.\n"
            f"Outils disponibles : {', '.join(self.outils_disponibles)}.\n\n"
            f"Demande utilisateur : \"{demande}\"\n\n"
            f"Reponds UNIQUEMENT avec un objet JSON valide, sans aucun texte autour, "
            f"exactement au format suivant :\n"
            f'{{"agent": "nom exact d\'un agent de la liste", '
            f'"difficulte": "faible|moyenne|elevee", '
            f'"risques": "aucun|faible|moyen|eleve", '
            f'"validation_requise": true ou false, '
            f'"resume": "resume court de l\'objectif en une phrase", '
            f'"outils_suggeres": ["liste des outils utiles parmi la liste, vide si aucun"]}}\n\n'
            f"validation_requise doit etre true uniquement si la demande modifie, supprime, cree des fichiers, "
            f"installe, deploie ou execute une action irreversible. "
            f"Pour une analyse, une explication, une idee, une planification ou une proposition, "
            f"validation_requise doit toujours etre false."
        )

        try:
            reponse = self.ai_engine.router.demander(prompt)
            reponse_nettoyee = self._nettoyer_json(reponse)
            data = json.loads(reponse_nettoyee)

            agent = data.get("agent", "00_directeur_ia")
            if agent not in liste_agents:
                agent = "00_directeur_ia"

            outils = data.get("outils_suggeres", [])
            outils = [o for o in outils if o in self.outils_disponibles]
            outils = filtrer_outils(agent, outils)

            return {
                "agent": agent,
                "analyse": {
                    "difficulte": data.get("difficulte", "moyenne"),
                    "risques": data.get("risques", "faible"),
                    "validation_requise": data.get("validation_requise", False),
                    "resume": data.get("resume", demande)
                },
                "outils_suggeres": outils
            }
        except Exception:
            return defaut

    def choisir_agent(self, demande):
        return self.decider(demande)["agent"]

    def obtenir_contexte_agent(self, nom_agent):
        return self.agent_manager.agents.get(nom_agent, "")
