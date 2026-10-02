import os
import json
import requests
from dotenv import load_dotenv
from ai_router import AIRouter
from tools import lire_fichier, ecrire_fichier, supprimer_fichier, lister_fichiers, creer_dossier, rechercher_web, creer_projet, ajouter_tache, lister_projets, lister_taches, terminer_tache, supprimer_tache, supprimer_projet, modifier_statut_projet, github_lister_repos, github_lire_fichier, github_ecrire_fichier

load_dotenv()

OUTILS = [
    {
        "type": "function",
        "function": {
            "name": "lire_fichier",
            "description": "Lit le contenu d'un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a lire"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ecrire_fichier",
            "description": "Ecrit ou remplace le contenu d'un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a ecrire"},
                    "contenu": {"type": "string", "description": "Contenu a ecrire dans le fichier"}
                },
                "required": ["chemin", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_fichier",
            "description": "Supprime definitivement un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a supprimer"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_fichiers",
            "description": "Liste les fichiers et dossiers presents dans un dossier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "dossier": {"type": "string", "description": "Chemin relatif du dossier a lister, par defaut le dossier racine"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creer_dossier",
            "description": "Cree un nouveau dossier dans le projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du dossier a creer"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_lister_repos",
            "description": "Liste les depots GitHub de l'utilisateur",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_lire_fichier",
            "description": "Lit le contenu d'un fichier depuis un depot GitHub",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Nom complet du depot, format utilisateur/repo"},
                    "chemin": {"type": "string", "description": "Chemin du fichier dans le depot"}
                },
                "required": ["repo", "chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_ecrire_fichier",
            "description": "Cree ou met a jour un fichier dans un depot GitHub avec un commit",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Nom complet du depot, format utilisateur/repo"},
                    "chemin": {"type": "string", "description": "Chemin du fichier dans le depot"},
                    "contenu": {"type": "string", "description": "Nouveau contenu du fichier"},
                    "message": {"type": "string", "description": "Message du commit"}
                },
                "required": ["repo", "chemin", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memoriser_info",
            "description": "Enregistre une information importante en memoire longue duree pour s en souvenir plus tard",
            "parameters": {
                "type": "object",
                "properties": {
                    "categorie": {"type": "string", "description": "Categorie: projets, decisions, preferences, connaissances ou erreurs"},
                    "contenu": {"type": "string", "description": "L information a memoriser"}
                },
                "required": ["categorie", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_souvenir",
            "description": "Recherche une information precedemment memorisee",
            "parameters": {
                "type": "object",
                "properties": {
                    "mot_cle": {"type": "string", "description": "Mot-cle a rechercher dans la memoire"}
                },
                "required": ["mot_cle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_web",
            "description": "Recherche des informations actuelles sur internet",
            "parameters": {
                "type": "object",
                "properties": {
                    "requete": {"type": "string", "description": "La requete de recherche"}
                },
                "required": ["requete"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creer_projet",
            "description": "Cree un nouveau projet dans le suivi de Jarvis",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet a creer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ajouter_tache",
            "description": "Ajoute une nouvelle tache dans le suivi de Jarvis",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache"},
                    "projet": {"type": "string", "description": "Le projet associe, optionnel"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_projets",
            "description": "Liste tous les projets enregistres",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_taches",
            "description": "Liste toutes les taches enregistrees",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminer_tache",
            "description": "Marque une tache comme terminee",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache a terminer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_tache",
            "description": "Supprime une tache du suivi",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache a supprimer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_projet",
            "description": "Supprime un projet du suivi",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet a supprimer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modifier_statut_projet",
            "description": "Modifie le statut d'un projet (en cours, en pause, termine, annule)",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet"},
                    "nouveau_statut": {"type": "string", "description": "Le nouveau statut : en cours, en pause, termine ou annule"}
                },
                "required": ["nom", "nouveau_statut"]
            }
        }
    }
]

FONCTIONS_DISPONIBLES = {
    "lire_fichier": lire_fichier,
    "ecrire_fichier": ecrire_fichier,
    "supprimer_fichier": supprimer_fichier,
    "lister_fichiers": lister_fichiers,
    "creer_dossier": creer_dossier,
    "github_lister_repos": github_lister_repos,
    "github_lire_fichier": github_lire_fichier,
    "github_ecrire_fichier": github_ecrire_fichier,
    "rechercher_web": rechercher_web,
    "creer_projet": creer_projet,
    "ajouter_tache": ajouter_tache,
    "lister_projets": lister_projets,
    "lister_taches": lister_taches,
    "terminer_tache": terminer_tache,
    "supprimer_tache": supprimer_tache,
    "supprimer_projet": supprimer_projet,
    "modifier_statut_projet": modifier_statut_projet
}


def _convertir_outils_gemini(outils):
    declarations = []
    for outil in outils:
        fonction = outil["function"]
        declarations.append({
            "name": fonction["name"],
            "description": fonction["description"],
            "parameters": fonction["parameters"]
        })
    return [{"functionDeclarations": declarations}]


OUTILS_GEMINI = _convertir_outils_gemini(OUTILS)


class AIEngine:
    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.derniers_resultats_outils = []

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "ai_providers.json"
        )

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.providers = {
            p["nom"]: p
            for p in config.get("providers", [])
        }

        groq = self.providers.get("groq", {})
        openrouter = self.providers.get("openrouter", {})
        gemini = self.providers.get("gemini", {})
        mistral = self.providers.get("mistral", {})

        self.api_key = os.getenv(groq.get("api_key_env", "GROQ_API_KEY"))
        self.url = groq.get("url")
        self.model = groq.get("model")

        self.openrouter_key = os.getenv(
            openrouter.get("api_key_env", "OPENROUTER_API_KEY")
        )
        self.openrouter_url = openrouter.get("url")
        self.openrouter_model = openrouter.get("model")

        self.gemini_key = os.getenv(
            gemini.get("api_key_env", "GEMINI_API_KEY")
        )
        self.gemini_url = gemini.get("url")

        self.mistral_key = os.getenv(
            mistral.get("api_key_env", "MISTRAL_API_KEY")
        )
        self.mistral_url = mistral.get("url")
        self.mistral_model = mistral.get("model")

        self.router = AIRouter(self)

    def demander(self, message, contexte="", historique=None, outils_autorises=None):
        self.derniers_resultats_outils = []
        ancien_outils_autorises = getattr(self, "outils_autorises", None)
        self.outils_autorises = outils_autorises
        try:
            return self.router.demander(message, contexte, historique)
        finally:
            self.outils_autorises = ancien_outils_autorises

    def _obtenir_outils_autorises(self):
        outils_autorises = getattr(self, "outils_autorises", None)

        if outils_autorises is None:
            return OUTILS

        return [
            outil for outil in OUTILS
            if outil.get("function", {}).get("name") in outils_autorises
        ]

    def _executer_outil(self, nom_fonction, arguments):
        outils_autorises = getattr(self, "outils_autorises", None)
        if outils_autorises is not None and nom_fonction not in outils_autorises:
            resultat = f"Erreur : loutil {nom_fonction} nest pas autorise pour cette execution."
            self.derniers_resultats_outils.append({"outil": nom_fonction, "resultat": str(resultat)})
            return resultat
        if nom_fonction == "memoriser_info" and self.memory_manager:
            resultat = self.memory_manager.memoriser(arguments.get("categorie"), arguments.get("contenu"))
        elif nom_fonction == "rechercher_souvenir" and self.memory_manager:
            resultat = self.memory_manager.rechercher_souvenir(arguments.get("mot_cle"))
        else:
            fonction = FONCTIONS_DISPONIBLES.get(nom_fonction)
            resultat = fonction(**arguments) if fonction else "Outil inconnu."
        self.derniers_resultats_outils.append({"outil": nom_fonction, "resultat": str(resultat)})
        return resultat

    def _appeler_openai_compatible(self, url, headers, model, message, contexte="", historique=None, outils=None):
        messages = []
        if contexte:
            messages.append({"role": "system", "content": contexte})
        if historique:
            for echange in historique:
                messages.append({"role": "user", "content": echange["question"]})
                messages.append({"role": "assistant", "content": echange["reponse"]})
        messages.append({"role": "user", "content": message})

        for _ in range(5):
            payload = {"model": model, "messages": messages}
            if outils:
                payload["tools"] = outils
            reponse = requests.post(url, headers=headers, json=payload, timeout=30)
            reponse.raise_for_status()
            data = reponse.json()
            choix = data["choices"][0]["message"]

            if choix.get("tool_calls"):
                messages.append(choix)
                for appel in choix["tool_calls"]:
                    nom_fonction = appel["function"]["name"]
                    arguments = json.loads(appel["function"]["arguments"]) or {}
                    resultat = self._executer_outil(nom_fonction, arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": appel["id"],
                        "content": str(resultat)
                    })
            else:
                return choix["content"]

        raise Exception("Trop d'appels d'outils enchaines.")

    def _demander_groq(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.url, headers, self.model, message, contexte, historique, outils=self._obtenir_outils_autorises()
        )
    def _demander_openrouter(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.openrouter_url, headers, self.openrouter_model, message, contexte, historique, outils=self._obtenir_outils_autorises()
        )
    def _demander_mistral(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.mistral_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.mistral_url, headers, self.mistral_model, message, contexte, historique, outils=self._obtenir_outils_autorises()
        )

    def _demander_gemini(self, message, contexte="", historique=None):
        contents = []

        if historique:
            for echange in historique:
                contents.append({"role": "user", "parts": [{"text": echange["question"]}]})
                contents.append({"role": "model", "parts": [{"text": echange["reponse"]}]})

        contents.append({"role": "user", "parts": [{"text": message}]})

        payload = {"contents": contents, "tools": _convertir_outils_gemini(self._obtenir_outils_autorises())}
        if contexte:
            payload["systemInstruction"] = {"parts": [{"text": contexte}]}

        url = self.gemini_url + "?key=" + self.gemini_key

        for _ in range(5):
            reponse = requests.post(url, json=payload, timeout=30)
            reponse.raise_for_status()
            data = reponse.json()
            candidat = data["candidates"][0]["content"]

            appels_fonction = [p["functionCall"] for p in candidat.get("parts", []) if "functionCall" in p]

            if appels_fonction:
                contents.append(candidat)
                parts_resultats = []
                for appel in appels_fonction:
                    nom_fonction = appel["name"]
                    arguments = appel.get("args", {}) or {}
                    resultat = self._executer_outil(nom_fonction, arguments)
                    parts_resultats.append({
                        "functionResponse": {
                            "name": nom_fonction,
                            "response": {"resultat": str(resultat)}
                        }
                    })
                contents.append({"role": "user", "parts": parts_resultats})
                payload["contents"] = contents
            else:
                textes = [p.get("text", "") for p in candidat.get("parts", [])]
                return "[Secours Gemini] " + "".join(textes)

        raise Exception("Trop d'appels d'outils enchaines (Gemini).")
