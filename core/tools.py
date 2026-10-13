import unicodedata
import os
import difflib
import re
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


def _normaliser_nom_chemin(valeur):
    texte = unicodedata.normalize("NFKD", str(valeur))
    texte = texte.encode("ascii", "ignore").decode("ascii").lower()
    texte = texte.replace("\\", "/")
    mots = []
    for partie in texte.split("/"):
        partie = re.sub(r"^\d+[\s._-]*", "", partie)
        partie = re.sub(r"[_\-.]+", " ", partie)
        mots.extend(re.findall(r"[a-z0-9]+", partie))
    stop = {"de", "du", "des", "la", "le", "les", "un", "une", "d", "l", "a", "au", "aux", "et"}
    return " ".join(m for m in mots if m not in stop)


def _chercher_dossiers_similaires(dossier, limite=5):
    """Recherche des chemins proches, fichiers compris, dans le projet autorisé."""
    cible = _normaliser_nom_chemin(dossier)
    if not cible:
        return []

    exclusions = {
        ".git", ".patches", ".venv", "venv", "env", "node_modules",
        "__pycache__", ".pytest_cache"
    }
    resultats = []

    for racine, sous_dossiers, fichiers in os.walk(
        DOSSIER_AUTORISE, topdown=True, followlinks=False
    ):
        sous_dossiers[:] = [
            nom for nom in sous_dossiers
            if nom not in exclusions
            and _chemin_autorise(os.path.realpath(os.path.join(racine, nom)))
            and not _fichier_protege(os.path.realpath(os.path.join(racine, nom)))
        ]

        for nom in sous_dossiers + fichiers:
            chemin = os.path.join(racine, nom)
            reel = os.path.realpath(chemin)
            if not _chemin_autorise(reel) or _fichier_protege(reel):
                continue

            relatif = os.path.relpath(chemin, DOSSIER_AUTORISE)
            base = os.path.splitext(nom)[0] if os.path.isfile(chemin) else nom
            nom_normalise = _normaliser_nom_chemin(base)
            chemin_normalise = _normaliser_nom_chemin(
                os.path.splitext(relatif)[0] if os.path.isfile(chemin) else relatif
            )

            candidats = [x for x in (nom_normalise, chemin_normalise) if x]
            if not candidats:
                continue

            score = max(
                difflib.SequenceMatcher(None, cible, candidat).ratio()
                for candidat in candidats
            )

            mots_cible = cible.split()
            mots_nom = nom_normalise.split()
            if mots_cible and mots_nom:
                correspondance = sum(
                    1.0 if mot in mots_nom else max(
                        difflib.SequenceMatcher(None, mot, autre).ratio()
                        for autre in mots_nom
                    )
                    for mot in mots_cible
                ) / len(mots_cible)
                score = max(score, correspondance)

            if score >= 0.50:
                resultats.append((score, relatif))

    resultats.sort(key=lambda item: (-item[0], item[1].lower()))
    return [chemin for _, chemin in resultats[:limite]]

def creer_parent_manquant_pour_ecriture(chemin):
    """Cree un seul dossier parent manquant dans le projet autorise."""
    if not isinstance(chemin, str) or not chemin:
        return False

    chemin_complet = os.path.abspath(
        os.path.join(DOSSIER_AUTORISE, chemin)
    )
    if not _chemin_autorise(chemin_complet):
        return False

    chemin_reel = os.path.realpath(chemin_complet)
    if not _chemin_autorise(chemin_reel):
        return False
    if _fichier_protege(chemin_reel):
        return False
    if os.path.exists(chemin_reel):
        return False

    parent = os.path.dirname(chemin_reel)
    if os.path.isdir(parent) or not _chemin_autorise(parent):
        return False

    parent_reel = os.path.realpath(parent)
    if not _chemin_autorise(parent_reel):
        return False
    if _fichier_protege(parent_reel):
        return False

    parent_du_parent = os.path.dirname(parent_reel)
    if not os.path.isdir(parent_du_parent):
        return False
    if not _chemin_autorise(parent_du_parent):
        return False

    try:
        os.mkdir(parent_reel)
        return True
    except OSError:
        return False


def lire_fichier(chemin):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))

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
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)
    if not _chemin_autorise(chemin_reel):
        return "Erreur : accès refusé en dehors du projet."

    if _fichier_protege(chemin_reel):
        return f"Erreur : {chemin} est un fichier protege, modification refusee."

    dossier_parent = os.path.dirname(chemin_reel)
    if not os.path.isdir(dossier_parent):
        return f"Erreur : le dossier parent de {chemin} n'existe pas. Creez d'abord le dossier cible."

    if os.path.isdir(chemin_reel):
        return f"Erreur : {chemin} est un dossier, pas un fichier."

    if not isinstance(contenu, str):
        return "Erreur : le contenu du fichier doit être du texte."

    try:
        with open(chemin_reel, "w", encoding="utf-8") as f:
            f.write(contenu)

        with open(chemin_reel, "r", encoding="utf-8") as f:
            if f.read() != contenu:
                return f"Erreur : vérification échouée après écriture de {chemin}."

        return f"Fichier {chemin} écrit et vérifié avec succès."
    except (OSError, UnicodeError) as exc:
        return f"Erreur : impossible d'écrire ou de vérifier {chemin} : {exc}"

def supprimer_fichier(chemin):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))
    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."
    if _fichier_protege(chemin_complet):
        return f"Erreur : {chemin} est un fichier protege, suppression refusee."
    if not os.path.exists(chemin_complet):
        return f"Erreur : le fichier {chemin} n'existe pas, rien a supprimer."
    os.remove(chemin_complet)
    return f"Fichier {chemin} supprime avec succes."

def lister_fichiers(dossier="."):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, dossier))

    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."

    chemin_reel = os.path.realpath(chemin_complet)

    if _fichier_protege(chemin_reel):
        return "Erreur : accès refusé, dossier protégé."

    if not os.path.exists(chemin_reel):
        suggestions = _chercher_dossiers_similaires(dossier)
        if suggestions:
            liste = "\n".join(f"- {x}" for x in suggestions)
            return (
                f"Aucun dossier exact nommé '{dossier}' n'existe. "
                f"Chemins proches trouvés (fichiers et dossiers) :\n{liste}\n"
                "Vérifie le chemin proposé avant de réessayer. "
                "Aucun fichier ni dossier n'a été ouvert automatiquement."
            )
        return f"Erreur : le dossier {dossier} n'existe pas et aucun dossier proche n'a été trouvé."

    if not os.path.isdir(chemin_reel):
        return f"Erreur : {dossier} n'est pas un dossier."

    elements = os.listdir(chemin_reel)

    if not elements:
        return f"Le dossier {dossier} est vide."

    return "\n".join(sorted(elements))

def creer_dossier(chemin):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))

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


def lire_etat_projets_taches():
    """Retourne l'etat structure des projets et des taches."""
    return _charger_donnees()

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


def github_creer_repo(nom, description="", public=True):
    """
    Cree ou retrouve un depot GitHub via l'authentification locale de gh.

    L'operation est idempotente : si le depot existe deja avec la bonne
    visibilite, l'operation est consideree comme reussie.
    """
    import subprocess

    if not isinstance(nom, str) or not nom.strip():
        return "Erreur : le nom du depot est obligatoire."

    nom = nom.strip()

    if len(nom) > 100:
        return "Erreur : le nom du depot est trop long."

    if any(caractere in nom for caractere in (
        "/", "\\", " ", "\t", "\n", "\r", '"', "'", "`", "$"
    )):
        return "Erreur : nom de depot invalide."

    if not all(
        caractere.isalnum() or caractere in "-_."
        for caractere in nom
    ):
        return "Erreur : nom de depot invalide."

    if not isinstance(description, str):
        return "Erreur : la description doit etre une chaine."

    if len(description) > 500:
        return "Erreur : la description est trop longue."

    if not isinstance(public, bool):
        return "Erreur : public doit etre booleen."

    # Etape 1 : verifier si le depot existe deja.
    existant = subprocess.run(
        [
            "gh",
            "repo",
            "view",
            nom,
            "--json",
            "nameWithOwner,url,isPrivate",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if existant.returncode == 0:
        donnees = existant.stdout.strip()

        try:
            import json
            depot = json.loads(donnees)
        except json.JSONDecodeError:
            return (
                "Erreur : GitHub a retourne une reponse invalide "
                "lors de la verification du depot existant."
            )

        est_prive = depot.get("isPrivate")
        visibilite_attendue = not public

        if est_prive != visibilite_attendue:
            visibilite = "prive" if est_prive else "public"
            attendue = "prive" if not public else "public"
            return (
                f"Erreur : le depot {depot.get('nameWithOwner', nom)} "
                f"existe deja mais il est {visibilite}. "
                f"La demande exige un depot {attendue}."
            )

        return (
            f"Depot GitHub deja existant et verifie : "
            f"{donnees}"
        )

    # Le depot n'existe pas : on peut le creer.
    visibilite = "public" if public else "private"

    commande = [
        "gh",
        "repo",
        "create",
        nom,
        f"--{visibilite}",
        "--description",
        description,
    ]

    try:
        resultat = subprocess.run(
            commande,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return "Erreur : GitHub CLI 'gh' est introuvable."
    except subprocess.TimeoutExpired:
        return "Erreur : la creation du depot GitHub a expire."
    except OSError as erreur:
        return (
            "Erreur systeme GitHub CLI : "
            f"{type(erreur).__name__}: {erreur}"
        )

    sortie = (resultat.stdout or "").strip()
    erreur = (resultat.stderr or "").strip()

    if resultat.returncode != 0:
        details = erreur or sortie or "aucun detail fourni par gh"
        return f"Erreur creation depot GitHub : {details}"

    # Verification reelle apres creation.
    verification = subprocess.run(
        [
            "gh",
            "repo",
            "view",
            nom,
            "--json",
            "nameWithOwner,url,isPrivate",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if verification.returncode != 0:
        details = (
            verification.stderr.strip()
            or verification.stdout.strip()
            or "verification impossible"
        )
        return (
            "Erreur : le depot semble avoir ete cree, "
            f"mais sa verification a echoue : {details}"
        )

    return (
        f"Depot GitHub cree et verifie avec succes : "
        f"{verification.stdout.strip()}"
    )

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
    """
    Lit un fichier GitHub via l'authentification locale de GitHub CLI.

    Le depot peut etre fourni sous la forme :
    - "Dande-Lenol"
    - "utilisateur/Dande-Lenol"

    Aucun GITHUB_TOKEN n'est utilise.
    """
    import base64
    import json
    import subprocess

    if not isinstance(repo, str) or not repo.strip():
        return "Erreur : le depot GitHub est obligatoire."

    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : le chemin du fichier est obligatoire."

    repo = repo.strip()
    chemin = chemin.strip()

    if "/" not in repo:
        try:
            proprietaire = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError:
            return "Erreur : GitHub CLI 'gh' est introuvable."
        except subprocess.TimeoutExpired:
            return "Erreur : recuperation du compte GitHub expiree."
        except OSError as erreur:
            return (
                "Erreur systeme GitHub CLI : "
                f"{type(erreur).__name__}: {erreur}"
            )

        if proprietaire.returncode != 0:
            details = (
                proprietaire.stderr.strip()
                or proprietaire.stdout.strip()
                or "authentification GitHub indisponible"
            )
            return (
                "Erreur : impossible de recuperer le compte GitHub : "
                f"{details}"
            )

        login = proprietaire.stdout.strip()

        if not login:
            return (
                "Erreur : le compte GitHub authentifie "
                "est introuvable."
            )

        repo = f"{login}/{repo}"

    chemin_api = f"repos/{repo}/contents/{chemin}"

    try:
        lecture = subprocess.run(
            [
                "gh",
                "api",
                chemin_api,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        return "Erreur : GitHub CLI 'gh' est introuvable."
    except subprocess.TimeoutExpired:
        return "Erreur : lecture du fichier GitHub expiree."
    except OSError as erreur:
        return (
            "Erreur systeme GitHub CLI : "
            f"{type(erreur).__name__}: {erreur}"
        )

    if lecture.returncode != 0:
        details = (
            lecture.stderr.strip()
            or lecture.stdout.strip()
            or "aucun detail fourni par gh"
        )
        return (
            "Erreur lecture fichier GitHub : "
            f"{details}"
        )

    try:
        data = json.loads(lecture.stdout)
    except json.JSONDecodeError as erreur:
        return (
            "Erreur : reponse GitHub invalide : "
            f"{type(erreur).__name__}: {erreur}"
        )

    contenu_b64 = data.get("content")

    if not isinstance(contenu_b64, str) or not contenu_b64:
        return (
            "Erreur : GitHub n'a retourne aucun contenu "
            "pour ce fichier."
        )

    try:
        return base64.b64decode(contenu_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as erreur:
        return (
            "Erreur : impossible de decoder le contenu GitHub : "
            f"{type(erreur).__name__}: {erreur}"
        )


def github_ecrire_fichier(
    repo,
    chemin,
    contenu,
    message="Mise a jour via Jarvis",
):
    """
    Cree ou met a jour un fichier GitHub via l'authentification locale gh.

    Le depot peut etre fourni sous la forme :
    - "Dande-Lenol"
    - "utilisateur/Dande-Lenol"

    Aucun GITHUB_TOKEN n'est utilise.
    """
    import json
    import subprocess

    if not isinstance(repo, str) or not repo.strip():
        return "Erreur : le depot GitHub est obligatoire."

    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : le chemin du fichier est obligatoire."

    if not isinstance(contenu, str):
        return "Erreur : le contenu du fichier doit etre une chaine."

    if not isinstance(message, str) or not message.strip():
        return "Erreur : le message du commit est obligatoire."

    repo = repo.strip()
    chemin = chemin.strip()
    message = message.strip()

    if "/" not in repo:
        try:
            proprietaire = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except FileNotFoundError:
            return "Erreur : GitHub CLI 'gh' est introuvable."
        except subprocess.TimeoutExpired:
            return "Erreur : recuperation du compte GitHub expiree."
        except OSError as erreur:
            return (
                "Erreur systeme GitHub CLI : "
                f"{type(erreur).__name__}: {erreur}"
            )

        if proprietaire.returncode != 0:
            details = (
                proprietaire.stderr.strip()
                or proprietaire.stdout.strip()
                or "authentification GitHub indisponible"
            )
            return f"Erreur : impossible de recuperer le compte GitHub : {details}"

        login = proprietaire.stdout.strip()

        if not login:
            return "Erreur : le compte GitHub authentifie est introuvable."

        repo = f"{login}/{repo}"

    contenu_b64 = base64.b64encode(
        contenu.encode("utf-8")
    ).decode("utf-8")

    chemin_api = f"repos/{repo}/contents/{chemin}"

    try:
        lecture = subprocess.run(
            [
                "gh",
                "api",
                chemin_api,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        return "Erreur : GitHub CLI 'gh' est introuvable."
    except subprocess.TimeoutExpired:
        return "Erreur : lecture du fichier GitHub expiree."
    except OSError as erreur:
        return (
            "Erreur systeme GitHub CLI : "
            f"{type(erreur).__name__}: {erreur}"
        )

    sha = None

    if lecture.returncode == 0:
        try:
            donnees = json.loads(lecture.stdout)
            sha = donnees.get("sha")
        except json.JSONDecodeError:
            return "Erreur : reponse GitHub invalide lors de la lecture du fichier."
    elif "HTTP 404" not in lecture.stderr:
        details = (
            lecture.stderr.strip()
            or lecture.stdout.strip()
            or "lecture GitHub impossible"
        )
        return f"Erreur GitHub : {details}"

    commande = [
        "gh",
        "api",
        chemin_api,
        "--method",
        "PUT",
        "-f",
        f"message={message}",
        "-f",
        f"content={contenu_b64}",
    ]

    if sha:
        commande.extend(["-f", f"sha={sha}"])

    try:
        resultat = subprocess.run(
            commande,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError:
        return "Erreur : GitHub CLI 'gh' est introuvable."
    except subprocess.TimeoutExpired:
        return "Erreur : ecriture du fichier GitHub expiree."
    except OSError as erreur:
        return (
            "Erreur systeme GitHub CLI : "
            f"{type(erreur).__name__}: {erreur}"
        )

    if resultat.returncode != 0:
        details = (
            resultat.stderr.strip()
            or resultat.stdout.strip()
            or "ecriture GitHub impossible"
        )
        return f"Erreur GitHub : {details}"

    return f"Fichier {chemin} envoye avec succes sur {repo}."

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
    import unicodedata
    from difflib import SequenceMatcher

    donnees = _charger_donnees()

    def normaliser_nom(valeur):
        texte = unicodedata.normalize("NFKD", str(valeur or "").strip().casefold())
        texte = "".join(c for c in texte if not unicodedata.combining(c))
        return " ".join(texte.split())

    nom_recherche = normaliser_nom(nom)
    projets_avant = donnees["projets"]

    correspondances = [
        p for p in projets_avant
        if isinstance(p, dict)
        and normaliser_nom(p.get("nom", "")) == nom_recherche
    ]

    if not correspondances:
        ressemblances = [
            str(p.get("nom", "")).strip()
            for p in projets_avant
            if isinstance(p, dict)
            and isinstance(p.get("nom"), str)
            and SequenceMatcher(
                None, nom_recherche, normaliser_nom(p["nom"])
            ).ratio() >= 0.70
        ]
        if ressemblances:
            return (
                f"Confirmation requise : le nom '{nom}' ne correspond pas exactement. "
                f"Projet ressemblant trouvé : {', '.join(ressemblances)}. "
                "Aucun projet n'a été supprimé. Confirme le nom exact."
            )
        return f"Erreur : projet '{nom}' introuvable."

    if len(correspondances) > 1:
        return (
            f"Erreur : plusieurs projets correspondent à '{nom}'. "
            "Aucun projet n'a été supprimé."
        )

    projet_cible = correspondances[0]
    donnees["projets"] = [
        p for p in projets_avant if p is not projet_cible
    ]
    _sauvegarder_donnees(donnees)
    return f"Projet '{projet_cible.get('nom', nom)}' supprime avec succes."

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


def executer_tests_python():
    """Execute uniquement la suite unittest du depot, avec un delai limite."""
    import subprocess
    import sys

    dossier_tests = os.path.join(DOSSIER_AUTORISE, "tests")
    if not os.path.isdir(dossier_tests):
        return "Erreur : le dossier tests est introuvable."

    commande = [
        sys.executable, "-m", "unittest", "discover",
        "-s", "tests", "-p", "test*.py"
    ]

    try:
        resultat = subprocess.run(
            commande,
            cwd=DOSSIER_AUTORISE,
            capture_output=True,
            text=True,
            timeout=90,
            check=False
        )
    except subprocess.TimeoutExpired:
        return "Tests interrompus : délai maximal de 90 secondes dépassé."
    except OSError as exc:
        return f"Erreur lors du lancement des tests : {exc}"

    sortie = (resultat.stdout or "") + "\n" + (resultat.stderr or "")
    sortie = sortie.strip()[-12000:]

    if resultat.returncode == 0:
        return "SUCCÈS : tous les tests ont réussi.\n" + sortie

    return (
        f"ÉCHEC : les tests ont retourné le code {resultat.returncode}.\n"
        + sortie
    )
