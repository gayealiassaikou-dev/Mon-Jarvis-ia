import os
import json
import requests
import base64

DOSSIER_AUTORISE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _chemin_autorise(chemin_complet):
    chemin_reel = os.path.realpath(chemin_complet)
    dossier_reel = os.path.realpath(DOSSIER_AUTORISE)

    try:
        return os.path.commonpath(
            [chemin_reel, dossier_reel]
        ) == dossier_reel
    except ValueError:
        return False

FICHIERS_PROTEGES = [
    os.path.join(DOSSIER_AUTORISE, ".env"),
    os.path.join(DOSSIER_AUTORISE, ".git"),
]

DOSSIERS_PROTEGES = [
    os.path.join(DOSSIER_AUTORISE, "core"),
]

def _fichier_protege(chemin_complet):
    for proteg in FICHIERS_PROTEGES:
        if chemin_complet == proteg:
            return True
    for dossier in DOSSIERS_PROTEGES:
        try:
            if os.path.commonpath([chemin_complet, dossier]) == dossier:
                return True
        except ValueError:
            continue
    return False

def lire_fichier(chemin):
    chemin_complet = os.path.abspath(chemin)

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : accès refusé, fichier ou dossier protégé."

    if not os.path.exists(chemin_reel):
        return f"Erreur : le fichier {chemin} n'existe pas."

    with open(chemin_reel, "r", encoding="utf-8") as f:
        return f.read()

def ecrire_fichier(chemin, contenu):
    chemin_complet = os.path.abspath(chemin)
    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."
    if _fichier_protege(chemin_complet):
        return f"Erreur : {chemin} est un fichier protege, modification refusee."
    with open(chemin_complet, "w", encoding="utf-8") as f:
        f.write(contenu)
    return f"Fichier {chemin} écrit avec succès."

def supprimer_fichier(chemin):
    chemin_complet = os.path.abspath(chemin)
    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."
    if _fichier_protege(chemin_complet):
        return f"Erreur : {chemin} est un fichier protege, suppression refusee."
    if not os.path.exists(chemin_complet):
        return f"Erreur : le fichier {chemin} n'existe pas, rien a supprimer."
    os.remove(chemin_complet)
    return f"Fichier {chemin} supprime avec succes."

def lister_fichiers(dossier="."):
    chemin_complet = os.path.abspath(dossier)

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : accès refusé, dossier protégé."

    if not os.path.exists(chemin_reel):
        return f"Erreur : le dossier {dossier} n'existe pas."

    if not os.path.isdir(chemin_reel):
        return f"Erreur : {dossier} n'est pas un dossier."

    elements = os.listdir(chemin_reel)

    if not elements:
        return f"Le dossier {dossier} est vide."

    return "\n".join(sorted(elements))

def creer_dossier(chemin):
    chemin_complet = os.path.abspath(chemin)

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : création refusée dans un dossier protégé."

    if os.path.exists(chemin_reel):
        return f"Le dossier {chemin} existe deja."

    os.makedirs(chemin_reel)

    return f"Dossier {chemin} cree avec succes."

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
            texte += f"- {r.get('title')}: {r.get('content')[:200]}\n"
        return texte if texte else "Aucun resultat trouve pour cette recherche."
    except requests.exceptions.Timeout:
        return "Erreur : la recherche web a expire (timeout)."
    except requests.exceptions.ConnectionError:
        return "Erreur : impossible de se connecter a Tavily (verifie ta connexion internet)."
    except Exception as e:
        return f"Erreur recherche web inattendue : {e}"

CHEMIN_DONNEES = os.path.join("data", "projets_taches.json")

def _charger_donnees():
    if not os.path.exists(CHEMIN_DONNEES):
        return {"projets": [], "taches": []}
    try:
        with open(CHEMIN_DONNEES, "r", encoding="utf-8") as f:
            donnees = json.load(f)
            donnees.setdefault("projets", [])
            donnees.setdefault("taches", [])
            return donnees
    except (json.JSONDecodeError, ValueError):
        return {"projets": [], "taches": []}

def _sauvegarder_donnees(donnees):
    os.makedirs(os.path.dirname(CHEMIN_DONNEES), exist_ok=True)
    with open(CHEMIN_DONNEES, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=4, ensure_ascii=False)

def creer_projet(nom):
    donnees = _charger_donnees()
    for p in donnees["projets"]:
        if p["nom"].strip().lower() == nom.strip().lower():
            return f"Erreur : le projet '{nom}' existe deja."
    donnees["projets"].append({"nom": nom, "statut": "en cours"})
    _sauvegarder_donnees(donnees)
    return f"Projet '{nom}' cree avec succes."

def ajouter_tache(nom, projet=""):
    donnees = _charger_donnees()
    for t in donnees["taches"]:
        if t["nom"].strip().lower() == nom.strip().lower() and t["projet"].strip().lower() == projet.strip().lower():
            return f"Erreur : la tache '{nom}' existe deja pour ce projet."
    donnees["taches"].append({"nom": nom, "projet": projet, "statut": "en attente"})
    _sauvegarder_donnees(donnees)
    return f"Tache '{nom}' ajoutee avec succes."

def lister_projets():
    donnees = _charger_donnees()
    if not donnees["projets"]:
        return "Aucun projet enregistre."
    texte = ""
    for p in donnees["projets"]:
        texte += f"- {p['nom']} ({p['statut']})\n"
    return texte

def lister_taches():
    donnees = _charger_donnees()
    if not donnees["taches"]:
        return "Aucune tache enregistree."
    texte = ""
    for t in donnees["taches"]:
        texte += f"- {t['nom']} [{t['statut']}]"
        if t["projet"]:
            texte += f" (projet: {t['projet']})"
        texte += "\n"
    return texte

def _headers_github():
    token = os.getenv("GITHUB_TOKEN")
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

def _interpreter_erreur_github(status_code, contexte=""):
    if status_code == 401:
        return "Erreur : token GitHub invalide ou expire."
    if status_code == 403:
        return "Erreur : acces refuse ou limite de requetes GitHub atteinte."
    if status_code == 404:
        return f"Erreur : {contexte} introuvable sur GitHub."
    return f"Erreur GitHub : code {status_code}."

def github_lister_repos():
    url = "https://api.github.com/user/repos"
    try:
        r = requests.get(url, headers=_headers_github(), timeout=15)
        if r.status_code != 200:
            return _interpreter_erreur_github(r.status_code, "les depots")
        repos = r.json()
        if not repos:
            return "Aucun depot trouve."
        return "\n".join(f"- {repo['full_name']}" for repo in repos)
    except requests.exceptions.Timeout:
        return "Erreur : la connexion a GitHub a expire (timeout)."
    except requests.exceptions.ConnectionError:
        return "Erreur : impossible de se connecter a GitHub (verifie ta connexion internet)."
    except Exception as e:
        return f"Erreur GitHub inattendue : {e}"

def github_lire_fichier(repo, chemin):
    url = f"https://api.github.com/repos/{repo}/contents/{chemin}"
    try:
        r = requests.get(url, headers=_headers_github(), timeout=15)
        if r.status_code != 200:
            return _interpreter_erreur_github(r.status_code, f"le fichier {chemin} dans {repo}")
        data = r.json()
        contenu_b64 = data.get("content", "")
        contenu_decode = base64.b64decode(contenu_b64).decode("utf-8")
        return contenu_decode
    except requests.exceptions.Timeout:
        return "Erreur : la connexion a GitHub a expire (timeout)."
    except requests.exceptions.ConnectionError:
        return "Erreur : impossible de se connecter a GitHub (verifie ta connexion internet)."
    except Exception as e:
        return f"Erreur GitHub inattendue : {e}"

def github_ecrire_fichier(repo, chemin, contenu, message="Mise a jour via Jarvis"):
    url = f"https://api.github.com/repos/{repo}/contents/{chemin}"
    try:
        sha = None
        r_check = requests.get(url, headers=_headers_github(), timeout=15)
        if r_check.status_code == 200:
            sha = r_check.json().get("sha")
        elif r_check.status_code not in (200, 404):
            return _interpreter_erreur_github(r_check.status_code, f"le fichier {chemin} dans {repo}")

        contenu_b64 = base64.b64encode(contenu.encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": contenu_b64}
        if sha:
            payload["sha"] = sha

        r = requests.put(url, headers=_headers_github(), json=payload, timeout=15)
        if r.status_code not in (200, 201):
            return _interpreter_erreur_github(r.status_code, f"l'ecriture de {chemin} dans {repo}")
        return f"Fichier {chemin} envoye avec succes sur {repo}."
    except requests.exceptions.Timeout:
        return "Erreur : la connexion a GitHub a expire (timeout)."
    except requests.exceptions.ConnectionError:
        return "Erreur : impossible de se connecter a GitHub (verifie ta connexion internet)."
    except Exception as e:
        return f"Erreur GitHub inattendue : {e}"

def terminer_tache(nom):
    donnees = _charger_donnees()
    for t in donnees["taches"]:
        if t["nom"] == nom:
            t["statut"] = "terminee"
            _sauvegarder_donnees(donnees)
            return f"Tache '{nom}' marquee comme terminee."
    return f"Erreur : tache '{nom}' introuvable."

def supprimer_tache(nom):
    donnees = _charger_donnees()
    taille_avant = len(donnees["taches"])
    donnees["taches"] = [t for t in donnees["taches"] if t["nom"] != nom]
    if len(donnees["taches"]) == taille_avant:
        return f"Erreur : tache '{nom}' introuvable."
    _sauvegarder_donnees(donnees)
    return f"Tache '{nom}' supprimee avec succes."

def supprimer_projet(nom):
    donnees = _charger_donnees()
    taille_avant = len(donnees["projets"])
    donnees["projets"] = [p for p in donnees["projets"] if p["nom"] != nom]
    if len(donnees["projets"]) == taille_avant:
        return f"Erreur : projet '{nom}' introuvable."
    _sauvegarder_donnees(donnees)
    return f"Projet '{nom}' supprime avec succes."

def modifier_statut_projet(nom, nouveau_statut):
    statuts_valides = ["en cours", "en pause", "termine", "annule"]
    if nouveau_statut.strip().lower() not in statuts_valides:
        return f"Erreur : statut invalide. Statuts valides : {', '.join(statuts_valides)}."
    donnees = _charger_donnees()
    for p in donnees["projets"]:
        if p["nom"].strip().lower() == nom.strip().lower():
            p["statut"] = nouveau_statut.strip().lower()
            _sauvegarder_donnees(donnees)
            return f"Projet '{nom}' passe au statut '{nouveau_statut}'."
    return f"Erreur : projet '{nom}' introuvable."
