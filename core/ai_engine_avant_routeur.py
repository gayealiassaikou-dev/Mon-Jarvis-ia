import os
import json
import requests
from dotenv import load_dotenv
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
        self.api_key = os.getenv("GROQ_API_KEY")
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

    def demander(self, message, contexte="", historique=None):
        try:
            return self._demander_groq(message, contexte, historique)
        except Exception:
            try:
                return self._demander_gemini(message, contexte, historique)
            except Exception as e:
                return "Erreur IA (Groq et Gemini ont echoue) : " + str(e)

    def _executer_outil(self, nom_fonction, arguments):
        if nom_fonction == "memoriser_info" and self.memory_manager:
            return self.memory_manager.memoriser(arguments.get("categorie"), arguments.get("contenu"))
        if nom_fonction == "rechercher_souvenir" and self.memory_manager:
            return self.memory_manager.rechercher_souvenir(arguments.get("mot_cle"))
        fonction = FONCTIONS_DISPONIBLES.get(nom_fonction)
        return fonction(**arguments) if fonction else "Outil inconnu."

    def _demander_groq(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if contexte:
            messages.append({"role": "system", "content": contexte})

        if historique:
            for echange in historique:
                messages.append({"role": "user", "content": echange["question"]})
                messages.append({"role": "assistant", "content": echange["reponse"]})

        messages.append({"role": "user", "content": message})

        for _ in range(5):
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": OUTILS
            }
            reponse = requests.post(self.url, headers=headers, json=payload, timeout=30)
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

    def _demander_gemini(self, message, contexte="", historique=None):
        contents = []

        if historique:
            for echange in historique:
                contents.append({"role": "user", "parts": [{"text": echange["question"]}]})
                contents.append({"role": "model", "parts": [{"text": echange["reponse"]}]})

        contents.append({"role": "user", "parts": [{"text": message}]})

        payload = {"contents": contents, "tools": OUTILS_GEMINI}
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
