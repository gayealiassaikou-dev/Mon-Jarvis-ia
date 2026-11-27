"""Execution controlee d'un programme Python cree dans espace_travail/.

Le programme est lance par le lanceur enfant ``core/lanceur_python_c4.py``
(profil ``proot-degrade-v1``), avec un environnement filtre et un dossier
personnel par execution.

Etape 4 (V4/V5) : le parent cree une session dediee, draine ``stdout`` et
``stderr`` dans des threads bornes, applique une echeance murale puis tue le
groupe de processus (``SIGTERM`` -> grace -> ``SIGKILL``). Un chien de garde
scanne ``/proc`` pour tuer les descendants echappes par ``setsid``, uniquement
s'ils portent le marqueur ``JARVIS_EXEC_ID`` exact et si leur heure de
demarrage n'a pas change entre la detection et le signal (limite la
reutilisation de PID).

Etape 5 (V1, detection) : apres execution, le parent compare l'empreinte
(taille, mtime, hash sous 5 Mo) des fichiers proteges, cherche les valeurs
secretes connues (lues uniquement depuis ``.env``) dans les fichiers nouveaux
ou modifies de ``espace_travail/`` et deplace les fichiers contamines vers une
quarantaine hors de l'espace de travail (``/tmp/jarvis_c4_quarantaine``,
dossier 0700, fichiers 0600). Les valeurs secretes sont retirees des sorties et
des diagnostics avant retour au LLM.

Ces mesures sont de la **detection**, pas du confinement : elles sont
contournables par ``ctypes``/syscalls directs. La quarantaine appartient au
meme UID que le code execute : un programme qui decouvrirait son chemin
pourrait la lire malgre 0700/0600 ; elle est en revanche hors de portee des
outils fichiers (hors projet) et hors de ``espace_travail/``.

Ce nettoyage reste **au mieux** : si ``/proc`` est illisible (hidepid,
environnement non accessible), ``_ChienDeGarde.fiabilite`` vaut ``"partielle"``
ou ``"indisponible"`` et aucun descendant echappe n'est garanti nettoye.
"""
import base64
import errno
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid

from core.tools import DOSSIER_AUTORISE, _chemin_autorise, _fichier_protege
from core.tools_fichiers import DOSSIERS_PROTEGES, FICHIERS_PROTEGES

DOSSIER_EXECUTION = os.path.join(DOSSIER_AUTORISE, "espace_travail")
LANCEUR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "lanceur_python_c4.py"
)
DELAI_SECONDES = 30
GRACE_SECONDES = 2
TAILLE_MAX_FLUX = 64 * 1024
TAILLE_MAX_CUMULEE = 4 * 1024 * 1024
INTERVALLE_CHIEN_DE_GARDE = 0.5
BUDGET_PASSE_CHIEN_DE_GARDE = 0.4
ATTENTE_DRAIN = 1.0
VARIABLE_POLITIQUE = "JARVIS_C4_POLITIQUE"
VARIABLE_EXECUTION = "JARVIS_EXEC_ID"

# Etape 5 - integrite, detection de fuites et redaction.
FICHIER_SECRETS = os.path.join(DOSSIER_AUTORISE, ".env")
DOSSIER_QUARANTAINE = "/tmp/jarvis_c4_quarantaine"
MODE_QUARANTAINE = 0o700
MODE_FICHIER_QUARANTAINE = 0o600
TAILLE_MAX_HASH = 5 * 1024 * 1024
MAX_OCTETS_HASH = 4 * 1024 * 1024
MAX_FICHIERS_INTEGRITE = 4096
MAX_OCTETS_INTEGRITE = 64 * 1024 * 1024
MAX_FICHIERS_SCAN = 2048
TAILLE_MAX_SCAN = 5 * 1024 * 1024
MAX_OCTETS_SCAN = 32 * 1024 * 1024
LONGUEUR_MIN_SECRET = 8
MARQUE_REDACTION = "[REDACTE]"
DOSSIERS_AVERTISSEMENT = ("data", "memory")
RETENTION_QUARANTAINE_JOURS = 7  # indicatif : aucune purge automatique

# Liste blanche stricte : rien d'autre ne passe de l'environnement parent.
ENVIRONNEMENT_AUTORISE = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "LC_MESSAGES",
    "LC_NUMERIC",
    "LC_TIME",
    "TERM",
    "TZ",
    "USER",
    "LOGNAME",
    "SHELL",
)
VARIABLES_INTERDITES = frozenset({
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONEXECUTABLE",
    "LD_PRELOAD",
    "LD_LIBRARY_PATH",
})
MOTS_SECRETS = ("TOKEN", "KEY", "SECRET", "PASS", "API", "SUPABASE")

SOUS_DOSSIERS_EXECUTION = ("home", "tmp", "cache", "config", "data", "state")


def _variable_autorisee(nom):
    if nom in VARIABLES_INTERDITES:
        return False
    if any(mot in nom.upper() for mot in MOTS_SECRETS):
        return False
    return nom in ENVIRONNEMENT_AUTORISE


def _creer_dossier_execution():
    """Cree ``espace_travail/.exec_<id>/`` et ses sous-dossiers personnels."""
    base = os.path.join(DOSSIER_EXECUTION, f".exec_{uuid.uuid4().hex[:12]}")
    os.makedirs(base, mode=0o700)
    sous_dossiers = {}
    for nom in SOUS_DOSSIERS_EXECUTION:
        chemin = os.path.join(base, nom)
        os.makedirs(chemin, mode=0o700)
        sous_dossiers[nom] = chemin
    return base, sous_dossiers


def _environnement_propre(sous_dossiers):
    """Environnement enfant : liste blanche + dossier personnel par execution."""
    env = {
        nom: os.environ[nom]
        for nom in ENVIRONNEMENT_AUTORISE
        if nom in os.environ and _variable_autorisee(nom)
    }
    env.update({
        "HOME": sous_dossiers["home"],
        "TMPDIR": sous_dossiers["tmp"],
        "TEMP": sous_dossiers["tmp"],
        "TMP": sous_dossiers["tmp"],
        "XDG_CACHE_HOME": sous_dossiers["cache"],
        "XDG_CONFIG_HOME": sous_dossiers["config"],
        "XDG_DATA_HOME": sous_dossiers["data"],
        "XDG_STATE_HOME": sous_dossiers["state"],
    })
    politique = {
        "espace_travail": os.path.realpath(DOSSIER_EXECUTION),
        "proteges": list(FICHIERS_PROTEGES) + list(DOSSIERS_PROTEGES),
    }
    env[VARIABLE_POLITIQUE] = json.dumps(politique, separators=(",", ":"))
    return env


# ---------------------------------------------------------------------------
# Drains bornes (V5)
# ---------------------------------------------------------------------------
class _Drain:
    """Lit un tube jusqu'a EOF en ne conservant que ``TAILLE_MAX_FLUX``."""

    def __init__(self, flux):
        self.flux = flux
        self.morceaux = []
        self.total = 0
        self.tronquee = False
        self.verrou = threading.Lock()
        self.thread = threading.Thread(target=self._lire, daemon=True)

    def demarrer(self):
        self.thread.start()

    def _lire(self):
        try:
            while True:
                bloc = self.flux.read(8192)
                if not bloc:
                    break
                with self.verrou:
                    self.total += len(bloc)
                    if self.total <= TAILLE_MAX_FLUX:
                        self.morceaux.append(bloc)
                    else:
                        self.tronquee = True
                if self.total > TAILLE_MAX_CUMULEE:
                    # Le parent va arreter le programme (V5).
                    break
        except (OSError, ValueError):
            pass

    def cumul(self):
        with self.verrou:
            return self.total

    def contenu(self):
        with self.verrou:
            return b"".join(self.morceaux)


# ---------------------------------------------------------------------------
# Identite de processus et chien de garde (V4)
# ---------------------------------------------------------------------------
def _etat_et_demarrage(pid):
    """Retourne ``(etat, starttime)`` lus dans ``/proc/<pid>/stat``.

    ``starttime`` est le champ 22 (ticks apres le boot) : il identifie le
    demarrage du processus et permet de detecter une reutilisation de PID.
    Retourne ``(None, None)`` si ``/proc`` n'est pas lisible.
    """
    try:
        with open(f"/proc/{pid}/stat", "rb") as fichier:
            donnees = fichier.read(8192)
    except OSError:
        return None, None
    fin_nom = donnees.rfind(b")")
    if fin_nom < 0:
        return None, None
    champs = donnees[fin_nom + 2:].split()
    if len(champs) < 20:
        return None, None
    etat = champs[0].decode("ascii", "replace")
    demarrage = champs[19].decode("ascii", "replace")
    return etat, demarrage


def _marqueur_exact(pid, etiquette):
    """Vrai si ``/proc/<pid>/environ`` contient exactement le marqueur."""
    try:
        with open(f"/proc/{pid}/environ", "rb") as fichier:
            environ = fichier.read(262144)
    except OSError:
        return False
    attendu = VARIABLE_EXECUTION.encode() + b"=" + etiquette.encode()
    return any(entree == attendu for entree in environ.split(b"\0"))


class _ChienDeGarde(threading.Thread):
    """Tue les descendants marques, avec verification d'identite.

    Regles : jamais de kill sur un PID seul ; le marqueur doit etre exactement
    ``JARVIS_EXEC_ID=<etiquette>`` ; l'heure de demarrage lue avant la decision
    doit etre identique juste avant ``SIGKILL`` ; le processus racine n'est
    jamais vise (le parent gere son groupe). Chaque passe est bornee dans le
    temps et le total par ``BUDGET_PASSE_CHIEN_DE_GARDE``.
    """

    def __init__(self, etiquette, pid_racine, identite_racine):
        super().__init__(daemon=True)
        self.etiquette = etiquette
        self.pid_racine = pid_racine
        self.identite_racine = identite_racine
        self.tues = []
        self.fiabilite = "complete"
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            self._passe()
            self._stop.wait(INTERVALLE_CHIEN_DE_GARDE)
        # Passe finale : nettoyage des descendants nes juste avant la sortie.
        self._passe()

    def arreter(self):
        self._stop.set()
        self.join(timeout=BUDGET_PASSE_CHIEN_DE_GARDE + 1.0)

    def _passe(self):
        fin = time.monotonic() + BUDGET_PASSE_CHIEN_DE_GARDE
        try:
            entrees = os.listdir("/proc")
        except OSError:
            self.fiabilite = "indisponible"
            return

        for nom in entrees:
            if time.monotonic() > fin:
                return
            if not nom.isdigit():
                continue
            pid = int(nom)
            if pid == self.pid_racine:
                continue
            etat, demarrage = _etat_et_demarrage(pid)
            if demarrage is None:
                self.fiabilite = "partielle"
                continue
            if etat in ("Z", "X"):
                continue
            if (pid, demarrage) in self.tues:
                continue
            if self.identite_racine == (pid, demarrage):
                continue
            if not _marqueur_exact(pid, self.etiquette):
                continue

            # Re-verification juste avant le signal : PID + heure de demarrage.
            etat_final, demarrage_final = _etat_et_demarrage(pid)
            if demarrage_final is None or demarrage_final != demarrage:
                continue
            if etat_final in ("Z", "X"):
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                continue
            self.tues.append((pid, demarrage))


def _terminer_arbre(proc):
    """SIGTERM au groupe, grace, puis SIGKILL ; attente bornee."""
    try:
        pgid = os.getpgid(proc.pid)
    except OSError:
        pgid = None

    if pgid is not None and pgid == proc.pid:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            pass
        try:
            proc.wait(timeout=GRACE_SECONDES)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            pass
    else:
        try:
            proc.kill()
        except OSError:
            pass

    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        pass


def _fermer_tubes(proc):
    for flux in (proc.stdout, proc.stderr):
        try:
            flux.close()
        except (OSError, ValueError):
            pass


def _bloc_flux(titre, drain):
    texte = drain.contenu().decode("utf-8", "replace").strip()
    if drain.tronquee:
        texte += (
            f"\n[sortie tronquee a {TAILLE_MAX_FLUX} octets]"
        )
    return f"--- {titre} ---\n{texte}"


# ---------------------------------------------------------------------------
# Etape 5 - secrets, redaction et chemins (V1, detection)
# ---------------------------------------------------------------------------
def _sous(chemin, dossier):
    """Vrai si ``chemin`` est ``dossier`` ou l'un de ses descendants."""
    try:
        return os.path.commonpath([chemin, dossier]) == dossier
    except ValueError:
        return False


def _relatif(chemin):
    """Chemin relatif au projet si possible, sinon le chemin tel quel."""
    try:
        return os.path.relpath(chemin, DOSSIER_AUTORISE)
    except ValueError:
        return chemin


def _valeurs_secretes():
    """Valeurs connues lues uniquement dans ``.env`` (jamais retournees).

    Les lignes ``CLE=valeur`` sont acceptees ; les commentaires et les valeurs
    de moins de ``LONGUEUR_MIN_SECRET`` caracteres sont ignores pour ne pas
    masquer des mots courants. Toute erreur de lecture donne une liste vide.
    """
    try:
        with open(FICHIER_SECRETS, "r", encoding="utf-8", errors="replace") as f:
            lignes = f.readlines()
    except OSError:
        return ()

    valeurs = []
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        _, valeur = ligne.split("=", 1)
        valeur = valeur.strip().strip('"').strip("'")
        if len(valeur) >= LONGUEUR_MIN_SECRET and valeur not in valeurs:
            valeurs.append(valeur)
    return tuple(valeurs)


def _variantes_secretes(valeurs):
    """Formes recherchees : exacte, base64, hex minuscule et majuscule."""
    variantes = set()
    for valeur in valeurs:
        exacte = valeur.encode("utf-8", "replace")
        if len(exacte) < LONGUEUR_MIN_SECRET:
            continue
        variantes.add(exacte)
        variantes.add(base64.b64encode(exacte))
        variantes.add(exacte.hex().encode("ascii"))
        variantes.add(exacte.hex().upper().encode("ascii"))

    # Les formes les plus longues d'abord : evite qu'un remplacement partiel
    # empeche la detection d'une forme plus longue.
    return tuple(
        brute for brute in sorted(variantes, key=len, reverse=True) if brute
    )


def _rediger(texte, variantes):
    """Remplace chaque variante secrete par ``MARQUE_REDACTION``."""
    if not texte or not variantes:
        return texte
    for brute in variantes:
        if len(brute) < LONGUEUR_MIN_SECRET:
            continue
        motif = brute.decode("utf-8", "ignore")
        if not motif:
            continue
        texte = texte.replace(motif, MARQUE_REDACTION)
    return texte


def _dans_zone_avertissement(chemin):
    """Vrai pour ``data/`` et ``memory/`` : avertissement, pas echec (Q3)."""
    for nom in DOSSIERS_AVERTISSEMENT:
        base = os.path.join(DOSSIER_AUTORISE, nom)
        if chemin == base or _sous(chemin, base):
            return True
    return False


# ---------------------------------------------------------------------------
# Etape 5 - integrite des fichiers proteges (V2, detection)
# ---------------------------------------------------------------------------
def _hacher_fichier(chemin):
    """SHA256 du fichier, ou ``None`` si illisible."""
    try:
        h = hashlib.sha256()
        with open(chemin, "rb") as fichier:
            while True:
                bloc = fichier.read(65536)
                if not bloc:
                    break
                h.update(bloc)
        return h.hexdigest()
    except OSError:
        return None


def _racines_protegees():
    """Deduplique ``FICHIERS_PROTEGES`` + ``DOSSIERS_PROTEGES`` (chemins reels)."""
    racines = []
    for chemin in list(FICHIERS_PROTEGES) + list(DOSSIERS_PROTEGES):
        try:
            reel = os.path.realpath(chemin)
        except (OSError, ValueError):
            continue
        if reel not in racines:
            racines.append(reel)
    return racines


def _racine_git():
    """Chemin reel de ``.git`` s'il fait partie des fichiers proteges."""
    for chemin in FICHIERS_PROTEGES:
        if os.path.basename(os.path.normpath(chemin)) == ".git":
            return os.path.realpath(chemin)
    return None


def _empreinte_integrite():
    """Instantane borne des fichiers proteges : ``(dict, complet)``.

    Tous les fichiers enumeres ont ``(taille, mtime_ns, sha256|None)``. Le
    hash n'est calcule que pour les fichiers reguliers <= ``TAILLE_MAX_HASH``,
    dans l'ordre de priorite des racines, et jusqu'a ``MAX_OCTETS_HASH`` au
    total : au-dela (typiquement ``.git`` et ``.patches``), seuls taille et
    mtime sont releves (plafond de calcul, limite documentee).

    L'enumeration est bornee par ``MAX_FICHIERS_INTEGRITE`` et
    ``MAX_OCTETS_INTEGRITE`` ; au-dela, l'instantane est marque incomplet
    (avertissement, jamais echec).
    """
    chemins = []
    octets = 0
    complet = True
    racine_git = _racine_git()

    for racine in _racines_protegees():
        try:
            info = os.lstat(racine)
        except OSError:
            continue

        if not stat.S_ISDIR(info.st_mode):
            if len(chemins) >= MAX_FICHIERS_INTEGRITE:
                complet = False
                break
            chemins.append((racine, info.st_size, info.st_mtime_ns, info.st_mode))
            continue

        abandonne = False
        for dossier, sous_dossiers, fichiers in os.walk(
            racine, followlinks=False
        ):
            sous_dossiers[:] = [
                nom
                for nom in sous_dossiers
                if not os.path.islink(os.path.join(dossier, nom))
            ]
            for nom in fichiers:
                if (
                    len(chemins) >= MAX_FICHIERS_INTEGRITE
                    or octets >= MAX_OCTETS_INTEGRITE
                ):
                    complet = False
                    abandonne = True
                    break
                chemin = os.path.join(dossier, nom)
                try:
                    meta = os.lstat(chemin)
                except OSError:
                    continue
                if stat.S_ISDIR(meta.st_mode):
                    continue
                chemins.append(
                    (chemin, meta.st_size, meta.st_mtime_ns, meta.st_mode)
                )
                octets += meta.st_size
            if abandonne:
                break
        if abandonne:
            break

    # Priorite au hash : fichiers hors .git d'abord, .git en dernier, budget
    # global MAX_OCTETS_HASH (le cout d'I/O de .git est disproportionne).
    def _priorite(entree):
        if racine_git and _sous(entree[0], racine_git):
            return 1
        return 0

    empreinte = {}
    hashes = 0
    for chemin, taille, mtime_ns, mode in sorted(chemins, key=_priorite):
        valeur_hash = None
        if (
            stat.S_ISREG(mode)
            and taille <= TAILLE_MAX_HASH
            and hashes < MAX_OCTETS_HASH
        ):
            valeur_hash = _hacher_fichier(chemin)
            if valeur_hash is not None:
                hashes += taille
        empreinte[chemin] = (taille, mtime_ns, valeur_hash)

    return empreinte, complet


def _comparer_integrite(avant, complet_avant):
    """Compare l'instantane courant a ``avant`` ; retourne ``(ecarts, complet)``."""
    apres, complet = _empreinte_integrite()
    ecarts = []
    for chemin, infos in avant.items():
        if chemin not in apres:
            ecarts.append(("supprime", chemin))
        elif apres[chemin] != infos:
            ecarts.append(("modifie", chemin))
    for chemin in apres:
        if chemin not in avant:
            ecarts.append(("ajoute", chemin))
    return ecarts, (complet_avant and complet)


# ---------------------------------------------------------------------------
# Etape 5 - detection des fuites dans espace_travail
# ---------------------------------------------------------------------------
def _instantane_espace(dossier):
    """Etat ``(taille, mtime_ns)`` borne des fichiers de espace_travail."""
    etat = {}
    for racine, sous_dossiers, fichiers in os.walk(dossier, followlinks=False):
        sous_dossiers[:] = [
            nom
            for nom in sous_dossiers
            if not os.path.islink(os.path.join(racine, nom))
        ]
        for nom in fichiers:
            if len(etat) >= MAX_FICHIERS_SCAN:
                return etat
            chemin = os.path.join(racine, nom)
            try:
                info = os.lstat(chemin)
            except OSError:
                continue
            etat[chemin] = (info.st_size, info.st_mtime_ns)
    return etat


def _chercher_fuites(dossier, avant, variantes):
    """Fichiers nouveaux/modifies contenant une variante secrete.

    Seuls les fichiers absents de ``avant`` ou dont taille/mtime ont change
    sont lus. Budget global ``MAX_OCTETS_SCAN`` et par fichier
    ``TAILLE_MAX_SCAN`` ; les liens symboliques ne sont pas suivis.
    """
    if not variantes:
        return []

    fuites = []
    octets = 0
    examines = 0

    for racine, sous_dossiers, fichiers in os.walk(dossier, followlinks=False):
        sous_dossiers[:] = [
            nom
            for nom in sous_dossiers
            if not os.path.islink(os.path.join(racine, nom))
        ]
        for nom in fichiers:
            if examines >= MAX_FICHIERS_SCAN or octets >= MAX_OCTETS_SCAN:
                return fuites
            chemin = os.path.join(racine, nom)
            try:
                info = os.lstat(chemin)
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            if info.st_size > TAILLE_MAX_SCAN:
                continue
            if avant.get(chemin) == (info.st_size, info.st_mtime_ns):
                continue

            examines += 1
            try:
                with open(chemin, "rb") as fichier:
                    contenu = fichier.read(TAILLE_MAX_SCAN)
            except OSError:
                continue
            octets += len(contenu)
            if any(variante in contenu for variante in variantes):
                fuites.append({
                    "chemin": chemin,
                    "taille": len(contenu),
                    "sha256": hashlib.sha256(contenu).hexdigest(),
                })

    return fuites


# ---------------------------------------------------------------------------
# Etape 5 - quarantaine (hors espace_travail, 0700/0600, anti-symlink)
# ---------------------------------------------------------------------------
def _preparer_dossier_quarantaine(etiquette):
    """Cree/verifie la racine 0700 et le sous-dossier de l'execution.

    Levee ``OSError`` si la racine ou le sous-dossier n'est pas un vrai
    repertoire appartenant a l'utilisateur courant (protection anti-symlink).
    """
    os.makedirs(DOSSIER_QUARANTAINE, mode=MODE_QUARANTAINE, exist_ok=True)
    info = os.lstat(DOSSIER_QUARANTAINE)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise OSError(
            errno.EPERM, "racine de quarantaine non sure", DOSSIER_QUARANTAINE
        )
    os.chmod(DOSSIER_QUARANTAINE, MODE_QUARANTAINE)

    dossier = os.path.join(DOSSIER_QUARANTAINE, etiquette)
    os.makedirs(dossier, mode=MODE_QUARANTAINE, exist_ok=True)
    info = os.lstat(dossier)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise OSError(errno.EPERM, "dossier de quarantaine non sur", dossier)
    os.chmod(dossier, MODE_QUARANTAINE)
    return dossier


def _mettre_en_quarantaine(chemin, etiquette):
    """Deplace ``chemin`` en quarantaine ; ``None`` si le deplacement echoue.

    En cas d'echec, le fichier contamine est supprime : aucun secret ne doit
    rester lisible dans ``espace_travail/``.
    """
    try:
        dossier = _preparer_dossier_quarantaine(etiquette)
    except OSError:
        dossier = None

    destination = None
    if dossier is not None:
        nom = hashlib.sha256(
            os.fsencode(chemin) + uuid.uuid4().bytes
        ).hexdigest()[:16]
        destination = os.path.join(dossier, nom + ".bin")
        if os.path.lexists(destination):
            destination = os.path.join(dossier, uuid.uuid4().hex + ".bin")
        try:
            try:
                os.replace(chemin, destination)
            except OSError as exc:
                if exc.errno != errno.EXDEV:
                    raise
                shutil.copy2(chemin, destination)
                os.unlink(chemin)
            os.chmod(destination, MODE_FICHIER_QUARANTAINE)
        except OSError:
            destination = None

    if destination is None:
        try:
            os.unlink(chemin)
        except OSError:
            pass
    return destination


def _resume_fuites(fuites):
    lignes = [
        "ECHEC : secret detecte dans "
        f"{len(fuites)} fichier(s) produit(s) par le programme."
    ]
    for fuite in fuites:
        etat = "mis en quarantaine" if fuite.get("quarantaine") else "supprime"
        lignes.append(
            f"- {_relatif(fuite['chemin'])} ({fuite['taille']} octets, "
            f"sha256 {fuite['sha256'][:16]}...) : {etat}"
        )
    return "\n".join(lignes)


def _resume_integrite(ecarts):
    lignes = [
        "ECHEC : integrite des fichiers proteges modifiee "
        f"({len(ecarts)} constat(s))."
    ]
    for type_constat, chemin in ecarts[:20]:
        lignes.append(f"- {type_constat} : {_relatif(chemin)}")
    if len(ecarts) > 20:
        lignes.append(f"- ... {len(ecarts) - 20} autre(s) constat(s)")
    return "\n".join(lignes)


def _resume_avertissements(ecarts, complet):
    lignes = ["--- avertissement integrite (non bloquant) ---"]
    for type_constat, chemin in ecarts[:20]:
        lignes.append(f"- {type_constat} : {_relatif(chemin)}")
    if len(ecarts) > 20:
        lignes.append(f"- ... {len(ecarts) - 20} autre(s) constat(s)")
    if not complet:
        lignes.append(
            "- instantane d'integrite incomplet (plafonds de fichiers/octets)"
        )
    return "\n".join(lignes)


def _verifier_apres_execution(
    dossier_exec, espace_avant, integrite_avant, integrite_complet, variantes
):
    """Scan des fuites puis comparaison d'integrite ; jamais d'exception."""
    fuites = []
    ecarts = []
    complet = integrite_complet
    try:
        fuites = _chercher_fuites(dossier_exec, espace_avant, variantes)
    except Exception:
        fuites = []
    try:
        ecarts, complet = _comparer_integrite(integrite_avant, integrite_complet)
    except Exception:
        ecarts, complet = [], False
    return fuites, ecarts, complet


def _assainir(dossier_exec, espace_avant, integrite_avant, integrite_complet,
              variantes, etiquette):
    """Detection silencieuse (chemin d'echeance) : aucune sortie produite."""
    fuites, _, _ = _verifier_apres_execution(
        dossier_exec, espace_avant, integrite_avant, integrite_complet,
        variantes,
    )
    for fuite in fuites:
        _mettre_en_quarantaine(fuite["chemin"], etiquette)


def _executer_borne(reel, dossier_exec, sous_dossiers):
    etiquette = uuid.uuid4().hex
    env = _environnement_propre(sous_dossiers)
    env[VARIABLE_EXECUTION] = etiquette

    # Instantanes AVANT lancement : toute ecriture ulterieure est detectable.
    valeurs = _valeurs_secretes()
    variantes = _variantes_secretes(valeurs)
    integrite_avant, integrite_complet = _empreinte_integrite()
    espace_avant = _instantane_espace(dossier_exec)

    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-B", LANCEUR, reel],
            cwd=dossier_exec,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        return f"Erreur lors du lancement du programme : {exc}"

    _, identite_racine = _etat_et_demarrage(proc.pid)
    identite_racine = (
        (proc.pid, identite_racine) if identite_racine is not None else None
    )

    sortie = _Drain(proc.stdout)
    erreurs = _Drain(proc.stderr)
    sortie.demarrer()
    erreurs.demarrer()

    garde = _ChienDeGarde(etiquette, proc.pid, identite_racine)
    garde.start()

    fin = time.monotonic() + DELAI_SECONDES
    delai_depasse = False
    cumul_depasse = False

    while True:
        if proc.poll() is not None:
            break
        if sortie.cumul() + erreurs.cumul() > TAILLE_MAX_CUMULEE:
            cumul_depasse = True
            break
        if time.monotonic() >= fin:
            delai_depasse = True
            break
        time.sleep(0.05)

    if delai_depasse or cumul_depasse:
        _terminer_arbre(proc)

    for drain in (sortie, erreurs):
        drain.thread.join(timeout=ATTENTE_DRAIN)
    _fermer_tubes(proc)
    for drain in (sortie, erreurs):
        drain.thread.join(timeout=ATTENTE_DRAIN)

    garde.arreter()

    if delai_depasse:
        # Detection silencieuse et bornee : le message contractuel T12 reste
        # strictement identique, aucune sortie supplementaire.
        try:
            _assainir(
                dossier_exec, espace_avant, integrite_avant,
                integrite_complet, variantes, etiquette,
            )
        except Exception:
            pass
        return (
            f"Erreur : delai maximal de {DELAI_SECONDES} secondes depasse, "
            "programme interrompu."
        )

    fuites, ecarts, integrite_complete = _verifier_apres_execution(
        dossier_exec, espace_avant, integrite_avant, integrite_complet,
        variantes,
    )
    for fuite in fuites:
        destination = _mettre_en_quarantaine(fuite["chemin"], etiquette)
        fuite["quarantaine"] = destination is not None

    bloquants = [
        ecart for ecart in ecarts
        if not _dans_zone_avertissement(ecart[1])
    ]
    avertissements = [
        ecart for ecart in ecarts
        if _dans_zone_avertissement(ecart[1])
    ]

    code = proc.poll()
    if code is None:
        try:
            code = proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            code = None

    corps = _rediger(
        _bloc_flux("sortie", sortie)
        + "\n"
        + _bloc_flux("erreurs", erreurs),
        variantes,
    )
    if cumul_depasse:
        corps += (
            f"\n[execution interrompue : plus de {TAILLE_MAX_CUMULEE} octets "
            "de sortie cumules]"
        )

    if code == 0:
        resultat = "SUCCES : le programme s'est termine avec le code 0.\n" + corps
    elif code is None:
        resultat = (
            "ECHEC : le programme n'a pas pu etre recolte apres interruption.\n"
            + corps
        )
    else:
        diagnostic = "Aucun traceback exploitable."
        if erreurs.contenu():
            try:
                from core.tools import analyser_erreur_python
                diagnostic = analyser_erreur_python(
                    erreurs.contenu().decode("utf-8", "replace")
                )
            except Exception as exc:
                diagnostic = f"Diagnostic automatique indisponible : {exc}"
        resultat = (
            f"ECHEC : le programme a retourne le code {code}.\n"
            + corps
            + "\n--- diagnostic automatique ---\n"
            + _rediger(diagnostic, variantes)
        )

    entetes = []
    if fuites:
        entetes.append(_resume_fuites(fuites))
    if bloquants:
        entetes.append(_resume_integrite(bloquants))
    if entetes:
        return "\n\n".join(entetes) + "\n" + resultat

    if avertissements or not integrite_complete:
        return resultat + "\n\n" + _resume_avertissements(
            avertissements, integrite_complete
        )

    return resultat


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
        base, sous_dossiers = _creer_dossier_execution()
    except OSError as exc:
        return f"Erreur lors de la preparation de l'execution : {exc}"

    try:
        return _executer_borne(reel, dossier_exec, sous_dossiers)
    finally:
        shutil.rmtree(base, ignore_errors=True)
