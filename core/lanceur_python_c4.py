"""Lanceur enfant du profil ``proot-degrade-v1`` (chantier C4).

Stdlib uniquement. Le parent l'execute en mode isole, avant tout code
utilisateur :

    python -I -B core/lanceur_python_c4.py <script.py> [args...]

Ordre applique (identique a PLAN_C4.md §5) :

1. limites noyau (rlimits) ;
2. seccomp (filtre reseau ``proot-degrade-v1`` de l'etape 3) ;
3. hook d'audit (cloche avertisseuse, pas une barriere) ;
4. exec du code utilisateur.

Le filtre seccomp est installe reellement par ``installer_seccomp()`` :
sans libseccomp, il est construit a la main en BPF classique et pose par
``prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER)`` via ctypes. Si le noyau
refuse, la fonction retourne ``False``, ``capacites()`` documente la raison
et aucun message ne pretend que le filtre est actif.

Ce lanceur n'est pas une sandbox : proot n'est pas un outil de securite,
Landlock est indisponible (ENOSYS) et les namespaces sont emules.
Voir PLAN_C4.md (a) et (d) pour les limites assumees.
"""
import ctypes
import errno
import json
import os
import platform
import resource
import struct
import sys

PROFIL = "proot-degrade-v1"
ORDRE = ("rlimits", "seccomp", "hook_audit", "exec")
TAILLE_MO = 1024 * 1024

# (nom, limite douce, limite dure)
# RLIMIT_NPROC est volontairement absent : mesure sur ce Termux, il bloque
# tout l'UID Android (le premier fork echoue deja).
LIMITES = (
    ("RLIMIT_CORE", 0, 0),
    ("RLIMIT_NOFILE", 64, 64),
    ("RLIMIT_FSIZE", 8 * TAILLE_MO, 8 * TAILLE_MO),
    ("RLIMIT_AS", 512 * TAILLE_MO, 512 * TAILLE_MO),
    ("RLIMIT_CPU", 20, 25),
)

VARIABLE_POLITIQUE = "JARVIS_C4_POLITIQUE"
VARIABLE_ETAT_SECCOMP = "JARVIS_C4_SECCOMP"

# --- Filtre seccomp « proot-degrade-v1 » (etape 3) ---------------------
#
# Table nommee des numeros de syscall AArch64 (asm-generic/unistd.h) :
# le programme BPF ne contient aucun nombre de syscall en dur.
# AArch64 n'utilise pas socketcall : socket/connect/sendto sont directs.
SYSCALLS_AARCH64 = {
    "socket": 198,
    "connect": 203,
    "sendto": 206,
}

# Domaines dont la creation de socket est refusee en EPERM.
DOMAINES_REFUSES = {
    "AF_INET": 2,
    "AF_INET6": 10,
    "AF_NETLINK": 16,
    "AF_PACKET": 17,
    "AF_VSOCK": 40,
}
# AF_UNIX reste autorise (socketpair, IPC locale). Conseil : connect et
# sendto sont eux refuses pour tous les domaines (defense en profondeur),
# donc un AF_UNIX ne peut pas etre connecte ; socketpair reste utilisable.
DOMAINES_AUTORISES = {"AF_UNIX": 1}

ARCHITECTURES_AUDIT = {
    "aarch64": 0xC00000B7,  # AUDIT_ARCH_AARCH64
    "arm64": 0xC00000B7,
}

# Constantes BPF classiques et retours seccomp.
_BPF_LD_ABS = 0x20
_BPF_JEQ = 0x15
_BPF_RET = 0x06
_SECCOMP_RET_ALLOW = 0x7FFF0000
_SECCOMP_RET_EPERM = 0x00050000 | errno.EPERM
_SECCOMP_RET_KILL_PROCESS = 0x80000000
# struct seccomp_data : nr (0), arch (4), instruction_pointer (8), args (16).
_DECALAGE_NR = 0
_DECALAGE_ARCH = 4
_DECALAGE_ARG0 = 16

PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2

# Etat reel de la derniere installation dans CE processus. Les tests et
# les appelants lisent cet etat ; aucun succes n'est simule.
ETAT_SECCOMP = {
    "actif": False,
    "raison": "filtre non installe dans ce processus (installer_seccomp() non appele)",
}


def _seccomp_android_preexistant():
    """Rapporte si un filtre seccomp etait deja impose par l'environnement."""
    try:
        with open("/proc/self/status", encoding="utf-8") as statut:
            for ligne in statut:
                if ligne.startswith("Seccomp:"):
                    return ligne.split()[1] == "2"
    except OSError:
        return False
    return False


def capacites():
    """Rapporte les garanties reelles du profil, sans les surestimer."""
    return {
        "profil": PROFIL,
        "ordre": list(ORDRE),
        "limites": {
            nom: {"doux": doux, "dur": dur} for nom, doux, dur in LIMITES
        },
        "nproc": {
            "applique": False,
            "raison": "RLIMIT_NPROC bloque tout l'UID Android sur ce Termux",
        },
        "landlock": {
            "disponible": False,
            "raison": "landlock_create_ruleset renvoie ENOSYS (pas de controle par chemin)",
        },
        "namespaces": {
            "disponibles": False,
            "factices": True,
            "raison": "unshare -Ur donne uid=0 factice et CapEff=0 ; -p/-m/-n sont emules",
        },
        "seccomp": {
            "etat": "partiel",
            "actif": ETAT_SECCOMP["actif"],
            "raison": ETAT_SECCOMP["raison"],
            "mecanisme": (
                "prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER) + programme "
                "BPF classique construit a la main (libseccomp absent)"
            ),
            "libseccomp": False,
            "architecture": "AArch64 (AUDIT_ARCH_AARCH64)",
            "syscalls_refuses": {
                nom: numero for nom, numero in SYSCALLS_AARCH64.items()
            },
            "domaines_refuses": dict(DOMAINES_REFUSES),
            "domaines_autorises": dict(DOMAINES_AUTORISES),
            "filtre_android_preexistant": _seccomp_android_preexistant(),
            "limite": (
                "connect et sendto sont refuses pour tous les domaines, "
                "y compris AF_UNIX (defense en profondeur) ; le BPF ne voit "
                "pas la destination ; AF_UNIX reste creable (socketpair)"
            ),
        },
        "cgroups": {
            "disponibles": False,
            "raison": "/sys/fs/cgroup est inaccessible (Permission denied)",
        },
    }


def appliquer_rlimits():
    """Applique les limites noyau du profil et retourne celles posees."""
    appliquees = []
    for nom, doux, dur in LIMITES:
        constante = getattr(resource, nom, None)
        if constante is None:  # plateforme sans cette limite
            continue
        resource.setrlimit(constante, (doux, dur))
        appliquees.append(nom)
    return appliquees


class _SockFprog(ctypes.Structure):
    """struct sock_fprog (include/uapi/linux/filter.h)."""

    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]


def _offset_etiquette(cible, etiquettes, position):
    """Convertit une etiquette (ou un saut brut) en offset relatif BPF."""
    if cible is None:
        return 0
    if isinstance(cible, int):
        return cible
    return etiquettes[cible] - position - 1


def _assembler(instructions):
    """Assemble un programme BPF classique avec des etiquettes symboliques.

    Les sauts sont calcules, jamais comptes a la main : une erreur d'un
    seul octet dans un filtre seccomp refuserait la mauvaise chose.
    """
    etiquettes = {}
    position = 0
    for entree in instructions:
        if entree[0] == "label":
            etiquettes[entree[1]] = position
        else:
            position += 1

    programme = bytearray()
    position = 0
    for entree in instructions:
        if entree[0] == "label":
            continue
        _, code, jt, jf, k = entree
        programme += struct.pack(
            "<HBBI",
            code,
            _offset_etiquette(jt, etiquettes, position),
            _offset_etiquette(jf, etiquettes, position),
            k & 0xFFFFFFFF,
        )
        position += 1
    return bytes(programme)


def _programme_bpf(audit_arch):
    """Construit le filtre reseau ``proot-degrade-v1``.

    Regles (toute erreur d'architecture tue le processus au lieu de
    laisser passer un contournement par changement d'ABI) :

    - arch != AUDIT_ARCH_AARCH64 -> KILL_PROCESS ;
    - connect / sendto        -> EPERM ;
    - socket(domain, ...)     -> EPERM si domain est dans DOMAINES_REFUSES ;
    - tout le reste           -> ALLOW.
    """
    instructions = [
        ("ins", _BPF_LD_ABS, 0, 0, _DECALAGE_ARCH),
        ("ins", _BPF_JEQ, "suite", "tuer", audit_arch),
        ("label", "suite"),
        ("ins", _BPF_LD_ABS, 0, 0, _DECALAGE_NR),
        ("ins", _BPF_JEQ, "domaine", None, SYSCALLS_AARCH64["socket"]),
        ("ins", _BPF_JEQ, "refuser", None, SYSCALLS_AARCH64["connect"]),
        ("ins", _BPF_JEQ, "refuser", None, SYSCALLS_AARCH64["sendto"]),
        ("ins", _BPF_RET, 0, 0, _SECCOMP_RET_ALLOW),
        ("label", "domaine"),
        ("ins", _BPF_LD_ABS, 0, 0, _DECALAGE_ARG0),
    ]
    for domaine in DOMAINES_AUTORISES.values():
        instructions.append(("ins", _BPF_JEQ, "autoriser", None, domaine))
    for domaine in DOMAINES_REFUSES.values():
        instructions.append(("ins", _BPF_JEQ, "refuser", None, domaine))
    instructions.extend([
        ("ins", _BPF_RET, 0, 0, _SECCOMP_RET_ALLOW),
        ("label", "autoriser"),
        ("ins", _BPF_RET, 0, 0, _SECCOMP_RET_ALLOW),
        ("label", "refuser"),
        ("ins", _BPF_RET, 0, 0, _SECCOMP_RET_EPERM),
        ("label", "tuer"),
        ("ins", _BPF_RET, 0, 0, _SECCOMP_RET_KILL_PROCESS),
    ])
    return _assembler(instructions)


def _echec_seccomp(raison):
    """Enregistre un echec reel d'installation et retourne ``False``."""
    ETAT_SECCOMP.update(actif=False, raison=raison)
    return False


def installer_seccomp():
    """Installe le filtre reseau ``proot-degrade-v1`` dans ce processus.

    Sans libseccomp : programme BPF construit par :func:`_programme_bpf`,
    pose par ``prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER)`` via ctypes.
    Le filtre Android/PRoot deja present n'est ni contourne ni desactive.

    Retourne ``True`` seulement si le noyau a accepte le filtre ; sinon
    ``False`` avec une raison precise dans ``capacites()["seccomp"]``.
    """
    if ETAT_SECCOMP["actif"]:
        return True

    machine = platform.machine().lower()
    audit_arch = ARCHITECTURES_AUDIT.get(machine)
    if audit_arch is None:
        return _echec_seccomp(
            f"architecture {machine} non couverte : la table de numeros de "
            "syscall fournie est AArch64, filtre non installe"
        )

    programme = _programme_bpf(audit_arch)
    tampon = ctypes.create_string_buffer(programme, len(programme))
    filtre = _SockFprog(
        len(programme) // 8, ctypes.cast(tampon, ctypes.c_void_p)
    )

    try:
        libc = ctypes.CDLL(None, use_errno=True)
    except OSError as exc:
        return _echec_seccomp(f"libc introuvable via ctypes : {exc}")

    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        code = ctypes.get_errno()
        return _echec_seccomp(
            "prctl(PR_SET_NO_NEW_PRIVS) a echoue : "
            f"{errno.errorcode.get(code, 'errno')} ({code}), filtre non installe"
        )

    if libc.prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.byref(filtre), 0, 0) != 0:
        code = ctypes.get_errno()
        return _echec_seccomp(
            "prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER) a echoue : "
            f"{errno.errorcode.get(code, 'errno')} ({code}) ; "
            "le noyau ou le filtre Android/PRoot deja en place refuse "
            "l'ajout du filtre, seccomp est inactif"
        )

    ETAT_SECCOMP.update(
        actif=True,
        raison=(
            "filtre reseau proot-degrade-v1 installe par "
            "prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER) et accepte par le noyau ; "
            f"ENOSYS/EPERM non rencontres (uid={os.getuid()})"
        ),
    )
    return True


def _chemin_texte(valeur):
    """Convertit un argument d'audit en chemin absolu, ou None si inutilisable."""
    if isinstance(valeur, int):
        return None
    try:
        valeur = os.fspath(valeur)
    except TypeError:
        return None
    if isinstance(valeur, bytes):
        valeur = os.fsdecode(valeur)
    if not isinstance(valeur, str) or not valeur:
        return None
    if not os.path.isabs(valeur):
        valeur = os.path.join(os.getcwd(), valeur)
    return valeur


def _sous(chemin, dossier):
    try:
        return os.path.commonpath([chemin, dossier]) == dossier
    except ValueError:
        return False


def _en_ecriture(mode, drapeaux):
    if isinstance(mode, str):
        return any(caractere in mode for caractere in "wax+")
    if isinstance(drapeaux, int):
        return bool(
            drapeaux
            & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
    return False


def installer_hook_audit(espace_travail=None, proteges=()):
    """Installe un hook d'audit qui refuse les acces manifestement dangereux.

    Le hook est une cloche avertisseuse : il est contournable par ctypes ou
    par syscalls directs. Il refuse la lecture d'un chemin protege et toute
    ecriture hors de ``espace_travail``. Sans espace de travail fourni, il
    n'est pas installe et la fonction retourne ``False``.
    """
    if not espace_travail:
        return False

    espace = os.path.realpath(espace_travail)
    chemins_proteges = tuple(
        os.path.realpath(chemin) for chemin in proteges if chemin
    )

    def _protege(chemin):
        return any(
            chemin == protege or _sous(chemin, protege)
            for protege in chemins_proteges
        )

    def _refuser(message, chemin):
        raise PermissionError(
            errno.EACCES, f"{message} (profil {PROFIL})", chemin
        )

    def _hook(evenement, arguments):
        if evenement == "open":
            arguments = list(arguments) + [None, None, None]
            chemin = _chemin_texte(arguments[0])
            if chemin is None:
                return
            reel = os.path.realpath(chemin)
            ecriture = _en_ecriture(arguments[1], arguments[2])
            if ecriture:
                if not _sous(reel, espace):
                    _refuser("ecriture hors espace_travail refusee", chemin)
            elif _protege(reel):
                _refuser("lecture de fichier protege refusee", chemin)
            return

        if evenement in ("os.remove", "os.rmdir", "os.rename"):
            for valeur in arguments:
                chemin = _chemin_texte(valeur)
                if chemin is None:
                    continue
                reel = os.path.realpath(chemin)
                if not _sous(reel, espace):
                    _refuser("suppression hors espace_travail refusee", chemin)

    sys.addaudithook(_hook)
    return True


def _charger_politique():
    brut = os.environ.get(VARIABLE_POLITIQUE)
    if not brut:
        return {}
    try:
        politique = json.loads(brut)
    except (TypeError, ValueError):
        return {}
    return politique if isinstance(politique, dict) else {}


def executer_script(chemin, arguments):
    """Execute le script utilisateur dans le processus courant."""
    chemin = os.path.abspath(chemin)
    dossier = os.path.dirname(chemin)
    if dossier not in sys.path:
        sys.path.insert(0, dossier)

    sys.argv = [chemin] + list(arguments)
    with open(chemin, "rb") as fichier:
        code = compile(fichier.read(), chemin, "exec")

    espace_global = {
        "__name__": "__main__",
        "__file__": chemin,
        "__package__": None,
        "__builtins__": __builtins__,
    }
    exec(code, espace_global)


def principal(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("Erreur : lanceur sans script a executer.", file=sys.stderr)
        return 2

    script, arguments = argv[0], argv[1:]

    appliquer_rlimits()
    seccomp_actif = installer_seccomp()
    # Etat reel expose au code execute (aucun succes simule) : les tests
    # peuvent ainsi distinguer « filtre actif » d'un blocage preexistant.
    os.environ[VARIABLE_ETAT_SECCOMP] = "actif" if seccomp_actif else "inactif"
    if not seccomp_actif:
        print(
            "Avertissement : filtre seccomp inactif - "
            + ETAT_SECCOMP["raison"],
            file=sys.stderr,
        )
    politique = _charger_politique()
    installer_hook_audit(
        espace_travail=politique.get("espace_travail"),
        proteges=politique.get("proteges") or (),
    )
    executer_script(script, arguments)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
