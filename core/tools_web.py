"""Outils web - recherche Tavily."""
import os
import requests

from dotenv import load_dotenv
load_dotenv()


def rechercher_web(requete):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Erreur : cle API Tavily manquante (verifie le fichier .env)."

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": requete,
        "max_results": 3
    }
    try:
        reponse = requests.post(url, json=payload, timeout=15)
        if reponse.status_code == 401:
            return "Erreur : cle API Tavily invalide ou expiree."
        if reponse.status_code == 429:
            return "Erreur : limite de requetes Tavily atteinte, reessaie plus tard."
        if reponse.status_code != 200:
            return f"Erreur recherche web : code {reponse.status_code}."

        data = reponse.json()
        resultats = data.get("results", [])
        texte = ""
        for r in resultats:
            texte += f"- {r.get('title')}: {(r.get('content') or '')[:200]}\n  URL: {r.get('url')}\n"
        return texte if texte else "Aucun resultat trouve pour cette recherche."
    except requests.exceptions.Timeout:
        return "Erreur : la recherche web a expire (timeout)."
    except requests.exceptions.ConnectionError:
        return "Erreur : impossible de se connecter a Tavily (verifie ta connexion internet)."
    except Exception as e:
        return f"Erreur recherche web inattendue : {e}"
