"""Outils GitHub - API REST GitHub."""
import os
import json
import requests

from dotenv import load_dotenv
load_dotenv()


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


def github_creer_repo_original_en_ligne(nom, description="", public=True):
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


import functools as _ft
@_ft.wraps(github_creer_repo_original_en_ligne)
def github_creer_repo(*args, **kwargs):
    import shutil as _sh
    if not _sh.which('gh'):
        return "Erreur : cet outil GitHub n'est pas disponible en ligne (la commande gh n'est installee que sur le telephone). Aucune action effectuee."
    return github_creer_repo_original_en_ligne(*args, **kwargs)

def github_lister_repos_original_en_ligne():
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


import functools as _ft
@_ft.wraps(github_lister_repos_original_en_ligne)
def github_lister_repos(*args, **kwargs):
    import os as _os
    if not _os.getenv('GITHUB_TOKEN'):
        return 'Erreur : GITHUB_TOKEN est absent, impossible de lister les depots GitHub depuis ce serveur. Aucune action effectuee.'
    return github_lister_repos_original_en_ligne(*args, **kwargs)


def _github_resoudre_repo(repo):
    """Resout un depot GitHub et retourne son nom et le token disponible."""
    token = os.getenv("GITHUB_TOKEN", "").strip()

    if not isinstance(repo, str) or not repo.strip():
        return None, None, "Erreur : le depot GitHub est obligatoire."

    repo = repo.strip()

    if "/" not in repo:
        if not token:
            return None, None, (
                "Erreur : indique le depot sous la forme proprietaire/depot. "
                "Un GITHUB_TOKEN est necessaire pour resoudre un nom court."
            )
        try:
            reponse = requests.get(
                "https://api.github.com/user",
                headers=_github_entetes(token),
                timeout=15,
            )
        except requests.RequestException:
            return None, None, "Erreur : connexion a GitHub impossible."

        if reponse.status_code != 200:
            return None, None, (
                "Erreur GitHub : impossible de verifier le compte "
                f"(HTTP {reponse.status_code})."
            )

        repo = f"{reponse.json().get('login', '')}/{repo}"

    morceaux = repo.split("/")
    if (
        len(morceaux) != 2
        or not all(morceaux)
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", partie)
            for partie in morceaux
        )
    ):
        return None, None, (
            "Erreur : depot invalide. Utilise proprietaire/depot."
        )

    return repo, token, None


def _github_entetes(token=None):
    entetes = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        entetes["Authorization"] = f"Bearer {token}"
    return entetes


def _github_message_erreur(reponse):
    try:
        message = reponse.json().get("message")
    except (ValueError, AttributeError):
        message = None
    return str(message or "aucun detail fourni par GitHub")[:300]


def github_lire_fichier_original_en_ligne(repo, chemin):
    """Lit un fichier GitHub avec l'API REST officielle."""
    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : le chemin du fichier est obligatoire."

    chemin = chemin.strip().replace("\\", "/")
    if chemin.startswith("/") or ".." in chemin.split("/"):
        return "Erreur : chemin de fichier invalide."

    repo, token, erreur = _github_resoudre_repo(repo)
    if erreur:
        return erreur

    from urllib.parse import quote
    url = (
        "https://api.github.com/repos/"
        + quote(repo, safe="/")
        + "/contents/"
        + quote(chemin, safe="/")
    )

    try:
        reponse = requests.get(
            url, headers=_github_entetes(token), timeout=20
        )
    except requests.RequestException:
        return "Erreur : connexion a GitHub impossible pendant la lecture."

    if reponse.status_code != 200:
        return (
            f"Erreur lecture GitHub (HTTP {reponse.status_code}) : "
            f"{_github_message_erreur(reponse)}"
        )

    try:
        donnees = reponse.json()
        if donnees.get("type") != "file":
            return "Erreur : le chemin indique n'est pas un fichier."
        contenu = donnees.get("content", "")
        if not contenu:
            return "Erreur : GitHub n'a retourne aucun contenu."
        return base64.b64decode(contenu).decode("utf-8")
    except (ValueError, UnicodeDecodeError, TypeError, AttributeError):
        return "Erreur : contenu GitHub invalide ou non decodable."


def github_lire_fichier(*args, **kwargs):
    return github_lire_fichier_original_en_ligne(*args, **kwargs)


def github_ecrire_fichier_original_en_ligne(
    repo, chemin, contenu, message="Mise a jour via Sam Sarr"
):
    """Cree ou met a jour un fichier GitHub via l'API REST."""
    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : le chemin du fichier est obligatoire."
    if not isinstance(contenu, str):
        return "Erreur : le contenu du fichier doit etre une chaine."
    if not isinstance(message, str) or not message.strip():
        return "Erreur : le message du commit est obligatoire."

    chemin = chemin.strip().replace("\\", "/")
    if chemin.startswith("/") or ".." in chemin.split("/"):
        return "Erreur : chemin de fichier invalide."

    repo, token, erreur = _github_resoudre_repo(repo)
    if erreur:
        return erreur
    if not token:
        return (
            "Erreur : GITHUB_TOKEN est absent. "
            "Configure-le dans les variables d'environnement de Velixir."
        )

    from urllib.parse import quote
    url = (
        "https://api.github.com/repos/"
        + quote(repo, safe="/")
        + "/contents/"
        + quote(chemin, safe="/")
    )
    entetes = _github_entetes(token)

    try:
        lecture = requests.get(url, headers=entetes, timeout=20)
    except requests.RequestException:
        return "Erreur : connexion a GitHub impossible pendant la lecture."

    sha = None
    if lecture.status_code == 200:
        try:
            sha = lecture.json().get("sha")
        except (ValueError, AttributeError):
            return "Erreur : reponse GitHub invalide."
    elif lecture.status_code != 404:
        return (
            f"Erreur GitHub pendant la lecture (HTTP {lecture.status_code}) : "
            f"{_github_message_erreur(lecture)}"
        )

    donnees = {
        "message": message.strip(),
        "content": base64.b64encode(
            contenu.encode("utf-8")
        ).decode("ascii"),
    }
    if sha:
        donnees["sha"] = sha

    try:
        resultat = requests.put(
            url, headers=entetes, json=donnees, timeout=30
        )
    except requests.RequestException:
        return "Erreur : connexion a GitHub impossible pendant l'ecriture."

    if resultat.status_code not in (200, 201):
        return (
            f"Erreur ecriture GitHub (HTTP {resultat.status_code}) : "
            f"{_github_message_erreur(resultat)}"
        )

    return f"Fichier {chemin} envoye avec succes sur {repo}."


def github_ecrire_fichier(*args, **kwargs):
    return github_ecrire_fichier_original_en_ligne(*args, **kwargs)


