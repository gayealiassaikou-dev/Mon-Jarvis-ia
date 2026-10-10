import os
import requests
from dotenv import load_dotenv

load_dotenv()

def verifier_github():
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return "Erreur : token GitHub absent."

    url = "https://api.github.com/user"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        reponse = requests.get(url, headers=headers, timeout=10)
        reponse.raise_for_status()
        data = reponse.json()

        return f"Connexion GitHub réussie. Compte : {data.get('login')}"

    except Exception as e:
        return f"Erreur GitHub : {e}"
