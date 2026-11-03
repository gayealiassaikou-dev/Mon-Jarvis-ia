"""Execution controlee d'un programme Python cree dans espace_travail/."""
import os
import subprocess
import sys

from core.tools import DOSSIER_AUTORISE, _chemin_autorise, _fichier_protege

DOSSIER_EXECUTION = os.path.join(DOSSIER_AUTORISE, "espace_travail")
DELAI_SECONDES = 30
TAILLE_MAX_SORTIE = 12000
MOTS_SECRETS = ("KEY", "TOKEN", "SECRET", "PASS", "API", "SUPABASE")


def _environnement_propre():
    """Copie de l'environnement sans aucune variable qui ressemble a un secret."""
    env = {}
    for nom, valeur in os.environ.items():
        if any(mot in nom.upper() for mot in MOTS_SECRETS):
            continue
        env[nom] = valeur
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def executer_programme_python(chemin):
    """Execute un fichier .py de espace_travail/ et retourne le resultat reel."""
    if not isinstance(chemin, str) or not chemin.strip():
        return "Erreur : chemin du programme absent."

    chemin = chemin.strip()
    complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))
    reel = os.path.realpath(complet)

    if not _chemin_autorise(complet) or not _chemin_autorise(reel):
        return "Erreur : accès refusé en dehors du projet."

    if _fichier_protege(reel):
        return f"Erreur : {chemin} est un fichier protege, execution refusee."

    dossier_exec = os.path.realpath(DOSSIER_EXECUTION)
    try:
        dans_espace = os.path.commonpath([reel, dossier_exec]) == dossier_exec
    except ValueError:
        dans_espace = False
    if not dans_espace:
        return (
            "Erreur : seuls les programmes du dossier espace_travail "
            "peuvent etre executes."
        )

    if not reel.endswith(".py"):
        return f"Erreur : {chemin} n'est pas un fichier Python (.py)."

    if not os.path.isfile(reel):
        return f"Erreur : le fichier {chemin} n'existe pas."

    try:
        res = subprocess.run(
            [sys.executable, reel],
            cwd=dossier_exec,
            env=_environnement_propre(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=DELAI_SECONDES,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"Erreur : delai maximal de {DELAI_SECONDES} secondes depasse, programme interrompu."
    except OSError as exc:
        return f"Erreur lors du lancement du programme : {exc}"

    sortie = (res.stdout or "").strip()[-TAILLE_MAX_SORTIE:]
    erreurs = (res.stderr or "").strip()[-TAILLE_MAX_SORTIE:]
    corps = f"--- sortie ---\n{sortie}\n--- erreurs ---\n{erreurs}"

    if res.returncode == 0:
        return "SUCCES : le programme s'est termine avec le code 0.\n" + corps

    diagnostic = "Aucun traceback exploitable."
    if erreurs:
        try:
            from core.tools import analyser_erreur_python
            diagnostic = analyser_erreur_python(erreurs)
        except Exception as exc:
            diagnostic = f"Diagnostic automatique indisponible : {exc}"

    return (
        f"ECHEC : le programme a retourne le code {res.returncode}.\n"
        + corps
        + "\n--- diagnostic automatique ---\n"
        + diagnostic
    )
