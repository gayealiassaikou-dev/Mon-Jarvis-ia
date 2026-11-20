"""Business intelligence - recherche d'opportunites via Tavily."""
import os
import json
import re

import requests
from dotenv import load_dotenv

load_dotenv()


def _tavily(query, max_results=5):
    """Recherche Tavily, retourne liste de dicts {title, url, content}."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": max_results},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        return r.json().get("results", [])
    except Exception:
        return []


NICHES = {
    "redaction": {
        "requetes": [
            "freelance rédaction web tarif 2026 France",
            "site:fiverr.com article writing gig price",
            "site:upwork.com content writer hourly rate",
        ],
        "competences": ["rédaction", "SEO", "storytelling", "copywriting"],
    },
    "code": {
        "requetes": [
            "freelance développeur python tarif 2026",
            "site:fiverr.com python script automation price",
            "site:upwork.com python developer hourly rate",
        ],
        "competences": ["python", "automatisation", "scripts", "API"],
    },
    "traduction": {
        "requetes": [
            "freelance traduction français arabe tarif",
            "site:fiverr.com translation french arabic price",
            "site:upwork.com translator hourly rate french",
        ],
        "competences": ["français", "arabe", "anglais", "localisation"],
    },
    "data": {
        "requetes": [
            "freelance scraping data analyse tarif 2026",
            "site:fiverr.com web scraping data entry price",
            "site:upwork.com data analyst hourly rate",
        ],
        "competences": ["scraping", "Excel", "Python", "rapports"],
    },
}


def _extraire_prix(texte):
    """Cherche un prix en EUR/USD dans le texte."""
    m = re.findall(r"(\d{2,4})\s*(?:€|\$|EUR|USD|euros?)", texte, re.I)
    if not m:
        return None
    prix = [int(x) for x in m if 10 <= int(x) <= 5000]
    if not prix:
        return None
    return {"min": min(prix), "max": max(prix), "moyenne": sum(prix) // len(prix)}


def chercher_opportunites(niche):
    """Retourne un rapport structure pour une niche donnee."""
    niche = str(niche).lower().strip()
    if niche not in NICHES:
        return {
            "ok": False,
            "erreur": f"Niche inconnue: {niche}. Choix: {list(NICHES.keys())}",
        }

    config = NICHES[niche]
    tous_resultats = []
    prix_trouves = []

    for q in config["requetes"]:
        for r in _tavily(q, max_results=3):
            titre = r.get("title", "")
            contenu = r.get("content", "")[:300]
            url = r.get("url", "")
            prix = _extraire_prix(contenu)
            if prix:
                prix_trouves.append(prix)
            tous_resultats.append({
                "titre": titre[:100],
                "url": url,
                "extrait": contenu,
                "prix_detecte": prix,
            })

    # Agregation prix
    prix_agg = None
    if prix_trouves:
        prix_agg = {
            "min": min(p["min"] for p in prix_trouves),
            "max": max(p["max"] for p in prix_trouves),
            "moyenne": sum(p["moyenne"] for p in prix_trouves) // len(prix_trouves),
        }

    return {
        "ok": True,
        "niche": niche,
        "competences_requises": config["competences"],
        "prix_marche_detecte": prix_agg,
        "sources": tous_resultats[:6],
        "conseil": f"Teste cette niche avec 1 offre simple. Prix suggere: "
                   + (f"{prix_agg['moyenne']} EUR" if prix_agg else "a definir"),
    }
