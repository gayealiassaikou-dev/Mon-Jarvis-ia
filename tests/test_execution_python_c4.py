"""Tests C4 - confinement de l'execution Python.

Etape 1 : couche outils fichiers (V1/V2).
T35 - course TOCTOU : le chemin change entre le controle et l'ouverture.
T36 - lien dur vers un fichier protege : refus par controle d'inode.

Tous les tests sont offline (aucun @llm) et utilisent un dossier temporaire
sous espace_travail/, jamais de suppression de espace_travail/ lui-meme.

Etape 5 : T08 (limite V1), T37 (fuite mise en quarantaine) et T37b
(integrite d'un fichier protege).

Etape 6 (V7) : T25-T28 (fallback garde, plus de faux succes, hygiene
disque) et T38-T45 (liste blanche, contrat de retour, compatibilite
moteur factice, ContextVar, exception, concurrence, retry conditionne).
Ces tests sont ecrits avant l'implementation : ils doivent echouer tant
que `AIEngine.executer_outil_hors_llm` et `OUTILS_HORS_LLM` sont absents.
"""
import contextlib
import errno
import glob
import json
import os
import resource
import signal
import socket
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from core import execution_python, lanceur_python_c4, tools_fichiers
from core.ai_engine import AIEngine
from core.agent_permissions import TOUS_LES_OUTILS
from core.tool_guard import outil_connu
from core.tools_schema import FONCTIONS_DISPONIBLES

MARQUEUR = "SECRET_C4_NE_DOIT_PAS_SORTIR"
RACINE_PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _creer_lien_dur(source, cible):
    """Cree un lien dur (os.link absent de ce Python Termux)."""
    if hasattr(os, "link"):
        os.link(source, cible)
        return
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    resultat = libc.link(os.fsencode(source), os.fsencode(cible))
    if resultat != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), cible)


class TestFichiersC4(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=os.path.join(RACINE_PROJET, "espace_travail"),
            prefix="c4_fichiers_",
        )
        self.addCleanup(self.temp.cleanup)
        self.racine = os.path.realpath(self.temp.name)

        self.patch_racine = patch.object(
            tools_fichiers, "DOSSIER_AUTORISE", self.racine
        )
        self.patch_fichiers = patch.object(
            tools_fichiers,
            "FICHIERS_PROTEGES",
            [
                os.path.join(self.racine, ".env"),
                os.path.join(self.racine, ".supabase_session.json"),
                os.path.join(self.racine, ".git"),
            ],
        )
        self.patch_dossiers = patch.object(
            tools_fichiers,
            "DOSSIERS_PROTEGES",
            [
                os.path.join(self.racine, "core"),
                os.path.join(self.racine, ".git"),
                os.path.join(self.racine, "memory"),
                os.path.join(self.racine, "data"),
            ],
        )
        self.patch_racine.start()
        self.patch_fichiers.start()
        self.patch_dossiers.start()
        self.addCleanup(self.patch_dossiers.stop)
        self.addCleanup(self.patch_fichiers.stop)
        self.addCleanup(self.patch_racine.stop)

        self.ecrire(".env", MARQUEUR)
        self.ecrire("memory/secret.txt", MARQUEUR)
        self.ecrire("projet/cible.txt", "CONTENU_PUBLIC")
        os.makedirs(os.path.join(self.racine, "espace_travail"), exist_ok=True)

    def ecrire(self, chemin, contenu):
        complet = os.path.join(self.racine, chemin)
        os.makedirs(os.path.dirname(complet), exist_ok=True)
        with open(complet, "w", encoding="utf-8") as fichier:
            fichier.write(contenu)
        return complet

    def lire_direct(self, chemin):
        with open(os.path.join(self.racine, chemin), encoding="utf-8") as fichier:
            return fichier.read()

    # ------------------------------------------------------------------
    # T35 - course entre controle de chemin et ouverture
    # ------------------------------------------------------------------
    def test_T35_echange_de_lien_entre_controle_et_ouverture(self):
        """Le pre-controle voit un dossier sain, remplace par un lien apres.

        On neutralise volontairement `_pre_controler` pour simuler la fenetre
        de course. L'ouverture par descripteur doit refuser malgre tout.
        """
        try:
            os.symlink(
                os.path.join(self.racine, "memory"),
                os.path.join(self.racine, "projet", "lien"),
            )
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques indisponibles")

        chemin_piege = "projet/lien/secret.txt"

        with patch.object(tools_fichiers, "_pre_controler", return_value=None):
            lecture = tools_fichiers.lire_fichier(chemin_piege)
            self.assertTrue(lecture.startswith("Erreur"), lecture)
            self.assertNotIn(MARQUEUR, lecture)

            ecriture = tools_fichiers.ecrire_fichier(chemin_piege, "REMPLACE")
            self.assertTrue(ecriture.startswith("Erreur"), ecriture)
            self.assertEqual(self.lire_direct("memory/secret.txt"), MARQUEUR)

            suppression = tools_fichiers.supprimer_fichier(chemin_piege)
            self.assertTrue(suppression.startswith("Erreur"), suppression)
            self.assertEqual(self.lire_direct("memory/secret.txt"), MARQUEUR)

    # ------------------------------------------------------------------
    # T36 - lien dur vers un fichier protege
    # ------------------------------------------------------------------
    def test_T36_lien_dur_vers_env_refuse(self):
        lien_dur = os.path.join(self.racine, "espace_travail", "copie_env.txt")
        try:
            _creer_lien_dur(os.path.join(self.racine, ".env"), lien_dur)
        except (OSError, NotImplementedError):
            self.skipTest("liens durs indisponibles")

        lecture = tools_fichiers.lire_fichier("espace_travail/copie_env.txt")
        self.assertTrue(lecture.startswith("Erreur"), lecture)
        self.assertNotIn(MARQUEUR, lecture)

        ecriture = tools_fichiers.ecrire_fichier(
            "espace_travail/copie_env.txt", "REMPLACE"
        )
        self.assertTrue(ecriture.startswith("Erreur"), ecriture)
        self.assertEqual(self.lire_direct(".env"), MARQUEUR)

        # Le fichier ordinaire reste accessible : le refus vient de l'inode.
        self.assertEqual(
            tools_fichiers.lire_fichier("projet/cible.txt"), "CONTENU_PUBLIC"
        )


class _BaseExecutionC4(unittest.TestCase):
    """Cree les scripts de test sous espace_travail/, sans le supprimer."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=os.path.join(RACINE_PROJET, "espace_travail"),
            prefix="c4_exec_",
        )
        self.addCleanup(self.temp.cleanup)
        self.dossier = os.path.realpath(self.temp.name)

    def script(self, nom, source):
        chemin = os.path.join(self.dossier, nom)
        with open(chemin, "w", encoding="utf-8") as fichier:
            fichier.write(source)
        return os.path.relpath(chemin, RACINE_PROJET)

    def executer(self, source, nom="script_c4.py"):
        return execution_python.executer_programme_python(
            self.script(nom, source)
        )


class TestLanceurC4(_BaseExecutionC4):
    # ------------------------------------------------------------------
    # T01 - le profil annonce ses garanties reelles
    # ------------------------------------------------------------------
    def test_T01_profil_proot_degrade_v1_rapporte(self):
        capacites = lanceur_python_c4.capacites()

        self.assertEqual(capacites["profil"], "proot-degrade-v1")
        self.assertEqual(
            tuple(capacites["ordre"]),
            ("rlimits", "seccomp", "hook_audit", "exec"),
        )
        self.assertFalse(capacites["landlock"]["disponible"])
        self.assertFalse(capacites["namespaces"]["disponibles"])
        self.assertTrue(capacites["namespaces"]["factices"])
        self.assertEqual(capacites["seccomp"]["etat"], "partiel")
        self.assertFalse(capacites["seccomp"]["actif"])
        self.assertFalse(capacites["cgroups"]["disponibles"])

        limites = capacites["limites"]
        self.assertEqual(limites["RLIMIT_CORE"], {"doux": 0, "dur": 0})
        self.assertEqual(limites["RLIMIT_NOFILE"]["doux"], 64)
        self.assertEqual(limites["RLIMIT_FSIZE"]["doux"], 8 * 1024 * 1024)
        self.assertEqual(limites["RLIMIT_AS"]["doux"], 512 * 1024 * 1024)
        self.assertEqual(limites["RLIMIT_CPU"], {"doux": 20, "dur": 25})

    # ------------------------------------------------------------------
    # T02 - script hors espace_travail
    # ------------------------------------------------------------------
    def test_T02_script_hors_espace_travail_refuse(self):
        with tempfile.TemporaryDirectory(
            dir=RACINE_PROJET, prefix="c4_hors_"
        ) as dehors:
            chemin = os.path.join(dehors, "script.py")
            with open(chemin, "w", encoding="utf-8") as fichier:
                fichier.write("print('NE_DOIT_PAS_S_EXECUTER')\n")

            resultat = execution_python.executer_programme_python(
                os.path.relpath(chemin, RACINE_PROJET)
            )

        self.assertTrue(resultat.startswith("Erreur"), resultat)
        self.assertIn("espace_travail", resultat)
        self.assertNotIn("NE_DOIT_PAS_S_EXECUTER", resultat)

    # ------------------------------------------------------------------
    # T03 - script atteint par un lien symbolique
    # ------------------------------------------------------------------
    def test_T03_script_via_lien_symbolique_refuse(self):
        with tempfile.TemporaryDirectory(
            dir=RACINE_PROJET, prefix="c4_cible_"
        ) as dehors:
            cible = os.path.join(dehors, "cible.py")
            with open(cible, "w", encoding="utf-8") as fichier:
                fichier.write("print('CIBLE_ATTEINTE')\n")

            lien = os.path.join(self.dossier, "lien.py")
            try:
                os.symlink(cible, lien)
            except (OSError, NotImplementedError):
                self.skipTest("liens symboliques indisponibles")

            resultat = execution_python.executer_programme_python(
                os.path.relpath(lien, RACINE_PROJET)
            )

        self.assertTrue(resultat.startswith("Erreur"), resultat)
        self.assertNotIn("CIBLE_ATTEINTE", resultat)

    # ------------------------------------------------------------------
    # T04 - script protege (core/, memory/)
    # ------------------------------------------------------------------
    def test_T04_script_protege_refuse(self):
        for chemin in ("core/tools_fichiers.py", "memory/memory_index.db"):
            resultat = execution_python.executer_programme_python(chemin)
            self.assertTrue(resultat.startswith("Erreur"), resultat)
            self.assertIn("protege", resultat)

    # ------------------------------------------------------------------
    # T05 - extension non .py
    # ------------------------------------------------------------------
    def test_T05_extension_non_python_refusee(self):
        chemin = os.path.join(self.dossier, "script_c4.txt")
        with open(chemin, "w", encoding="utf-8") as fichier:
            fichier.write("print('TEXTE')\n")

        resultat = execution_python.executer_programme_python(
            os.path.relpath(chemin, RACINE_PROJET)
        )

        self.assertTrue(resultat.startswith("Erreur"), resultat)
        self.assertIn("Python (.py)", resultat)

    # ------------------------------------------------------------------
    # T06 - environnement filtre par liste blanche
    # ------------------------------------------------------------------
    def test_T06_variables_sensibles_absentes_de_l_enfant(self):
        source = (
            "import json, os\n"
            "print(json.dumps(dict(os.environ), sort_keys=True))\n"
            "print(os.environ.get('HOME', ''))\n"
            "print(os.environ.get('TMPDIR', ''))\n"
            "print(os.environ.get('XDG_CACHE_HOME', ''))\n"
        )
        environnement = {
            "C4_TOKEN_FACTICE": "VALEUR_TOKEN_INTERDITE",
            "OPENAI_API_KEY": "VALEUR_KEY_INTERDITE",
            "C4_VARIABLE_INCONNUE": "VALEUR_HORS_LISTE",
            "PYTHONPATH": self.dossier,
            "LD_PRELOAD": "/tmp/inexistant_c4.so",
        }
        with patch.dict(os.environ, environnement):
            resultat = self.executer(source, nom="env_c4.py")

        self.assertTrue(resultat.startswith("SUCCES"), resultat)
        for nom in environnement:
            self.assertNotIn(nom, resultat)
        self.assertNotIn("VALEUR_TOKEN_INTERDITE", resultat)
        self.assertNotIn("VALEUR_KEY_INTERDITE", resultat)
        self.assertNotIn("VALEUR_HORS_LISTE", resultat)
        self.assertIn(".exec_", resultat)

    # ------------------------------------------------------------------
    # T07 - import du projet impossible dans l'enfant
    # ------------------------------------------------------------------
    def test_T07_import_core_echoue(self):
        # Marqueur construit a l'execution : absent du source cite par le
        # diagnostic, donc sa presence signifierait que l'import a reussi.
        resultat = self.executer(
            "import core\nprint('IMPORT' + '_CORE_REUSSI')\n",
            nom="import_c4.py",
        )

        self.assertTrue(resultat.startswith("ECHEC"), resultat)
        self.assertIn("No module named 'core'", resultat)
        self.assertNotIn("IMPORT_CORE_REUSSI", resultat)


class TestSeccompC4(_BaseExecutionC4):
    """Etape 3 : filtre reseau ``proot-degrade-v1`` et hygiene des fd."""

    @staticmethod
    def _valeur(resultat, prefixe):
        for ligne in resultat.splitlines():
            if ligne.startswith(prefixe):
                return ligne[len(prefixe):].strip()
        return None

    def _exiger_seccomp_actif(self, resultat):
        """Echoue clairement si le filtre n'est pas actif dans l'enfant."""
        etat = self._valeur(resultat, "SECCOMP=")
        if etat != "actif":
            self.fail(
                "Filtre seccomp proot-degrade-v1 inactif dans le processus "
                f"enfant (etat={etat!r}) : le test ne peut pas prouver le "
                "blocage reseau.\n" + resultat
            )

    # ------------------------------------------------------------------
    # T09 - socket(AF_INET) refusee en EPERM par le filtre
    # ------------------------------------------------------------------
    def test_T09_socket_af_inet_bloquee(self):
        source = (
            "import errno, os, socket\n"
            "print('SECCOMP=' + os.environ.get('JARVIS_C4_SECCOMP', 'absent'))\n"
            "try:\n"
            "    socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "except OSError as exc:\n"
            "    print('TYPE=' + type(exc).__name__)\n"
            "    print('ERRNO=' + str(exc.errno))\n"
            "    print('CODE=' + errno.errorcode.get(exc.errno, 'INCONNU'))\n"
            "    print('MSG=' + str(exc))\n"
            "else:\n"
            "    print('SOCKET_AUTORISE')\n"
        )
        resultat = self.executer(source, nom="seccomp_t09.py")

        self.assertTrue(resultat.startswith("SUCCES"), resultat)
        self._exiger_seccomp_actif(resultat)
        self.assertNotIn("SOCKET_AUTORISE", resultat)
        self.assertEqual(
            self._valeur(resultat, "TYPE="), "PermissionError", resultat
        )
        # Preuve numerique : errno reel, pas seulement un texte.
        numero = self._valeur(resultat, "ERRNO=")
        self.assertIsNotNone(numero, resultat)
        self.assertEqual(int(numero), errno.EPERM, resultat)
        self.assertEqual(self._valeur(resultat, "CODE="), "EPERM", resultat)
        self.assertIn("Operation not permitted", resultat)

    # ------------------------------------------------------------------
    # T10 - urllib doit echouer sur EPERM, pas sur un refus de connexion
    # ------------------------------------------------------------------
    def test_T10_urllib_bloque_par_eperm(self):
        source = (
            "import os, urllib.request\n"
            "print('SECCOMP=' + os.environ.get('JARVIS_C4_SECCOMP', 'absent'))\n"
            "urllib.request.urlopen('http://127.0.0.1:1', timeout=5)\n"
        )
        resultat = self.executer(source, nom="seccomp_t10.py")

        self.assertTrue(resultat.startswith("ECHEC"), resultat)
        self.assertIn("code 1", resultat)
        self._exiger_seccomp_actif(resultat)
        # EPERM, et non un simple echec de connexion applicatif.
        self.assertIn("Errno 1", resultat)
        self.assertIn("Operation not permitted", resultat)
        self.assertNotIn("Connection refused", resultat)
        self.assertNotIn("Temporary failure in name resolution", resultat)

    # ------------------------------------------------------------------
    # T11 - aucun descripteur du parent herite par l'enfant
    # ------------------------------------------------------------------
    def test_T11_aucun_descripteur_du_parent_herite(self):
        source = (
            "import json, os\n"
            "descripteurs = {}\n"
            "for nom in os.listdir('/proc/self/fd'):\n"
            "    try:\n"
            "        descripteurs[nom] = os.readlink('/proc/self/fd/' + nom)\n"
            "    except OSError:\n"
            "        continue\n"
            "print('SECCOMP=' + os.environ.get('JARVIS_C4_SECCOMP', 'absent'))\n"
            "print('FDS=' + json.dumps(descripteurs, sort_keys=True))\n"
        )

        # Ressources ouvertes par le parent pendant l'execution : elles ne
        # doivent jamais apparaitre dans /proc/self/fd de l'enfant.
        gauche, droite = socket.socketpair()
        fichier_parent = tempfile.NamedTemporaryFile(
            dir=self.dossier, prefix="parent_c4_", delete=False
        )
        self.addCleanup(fichier_parent.close)
        self.addCleanup(lambda: os.path.exists(fichier_parent.name) and os.unlink(fichier_parent.name))
        try:
            resultat = self.executer(source, nom="seccomp_t11.py")
        finally:
            gauche.close()
            droite.close()

        self.assertTrue(resultat.startswith("SUCCES"), resultat)

        fds = json.loads(self._valeur(resultat, "FDS="))
        cibles = list(fds.values())

        # 1. Aucun socket du parent (ni d'ailleurs) : socketpair du parent
        #    ouvert pendant l'execution, `close_fds=True` et aucun
        #    descripteur transmis volontairement.
        self.assertEqual([c for c in cibles if c.startswith("socket:")], [], fds)
        # 2. Aucun fichier du parent (controle par chemin, puis par nom).
        self.assertNotIn(fichier_parent.name, " ".join(cibles), fds)

        # 3. stdin est bien /dev/null (stdin=DEVNULL), 1/2 sont les seuls
        #    tubes de capture crees par le parent : aucun tube en plus ne
        #    peut donc etre un tube herite.
        self.assertEqual(fds.get("0"), "/dev/null", fds)
        tubes = sorted(n for n, c in fds.items() if c.startswith("pipe:"))
        self.assertEqual(tubes, ["1", "2"], fds)

        # 4. Les descripteurs supplementaires appartiennent a l'enfant
        #    (bibliotheques chargees par son propre interpreteur, ex.
        #    libffi via ctypes) : ce ne sont pas des fuites du parent.
        for numero, cible in fds.items():
            if numero in ("0", "1", "2"):
                continue
            self.assertFalse(cible.startswith("socket:"), fds)
            self.assertNotEqual(cible, fichier_parent.name, fds)
            self.assertNotIn(str(self.dossier), cible, fds)


class TestRessourcesC4(_BaseExecutionC4):
    # ------------------------------------------------------------------
    # T20 - RLIMIT_FSIZE
    # ------------------------------------------------------------------
    def test_T20_taille_fichier_bornee(self):
        source = (
            "import os\n"
            "chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),\n"
            "                     'gros_c4.bin')\n"
            "with open(chemin, 'wb') as fichier:\n"
            "    fichier.write(b'x' * (10 * 1024 * 1024))\n"
            "print('ECRITURE_TERMINEE')\n"
        )
        resultat = self.executer(source, nom="fichier_c4.py")

        self.assertFalse(resultat.startswith("SUCCES"), resultat)
        chemin = os.path.join(self.dossier, "gros_c4.bin")
        self.assertTrue(os.path.exists(chemin))
        taille = os.path.getsize(chemin)
        self.assertGreater(taille, 0)
        self.assertLessEqual(taille, 8 * 1024 * 1024)

    # ------------------------------------------------------------------
    # T21 - RLIMIT_AS
    # ------------------------------------------------------------------
    def test_T21_memoire_virtuelle_bornee(self):
        source = (
            "try:\n"
            "    bloc = bytearray(2 * 1024 ** 3)\n"
            "    print('ALLOCATION_REUSSIE')\n"
            "except MemoryError:\n"
            "    print('MEMORYERROR')\n"
        )
        resultat = self.executer(source, nom="memoire_c4.py")

        self.assertIn("MEMORYERROR", resultat)
        self.assertNotIn("ALLOCATION_REUSSIE", resultat)

    # ------------------------------------------------------------------
    # T22 - RLIMIT_CPU
    # ------------------------------------------------------------------
    def test_T22_boucle_cpu_tuee(self):
        resultat = self.executer(
            "while True:\n    pass\n", nom="cpu_c4.py"
        )

        self.assertTrue(resultat.startswith("ECHEC"), resultat)
        # SIGXCPU (24) ou, a defaut, mur d'horloge du parent.
        self.assertTrue(
            "-24" in resultat or "delai maximal" in resultat, resultat
        )

    # ------------------------------------------------------------------
    # T23 - RLIMIT_NOFILE
    # ------------------------------------------------------------------
    def test_T23_descripteurs_limites(self):
        source = (
            "import errno\n"
            "ouverts = []\n"
            "try:\n"
            "    for _ in range(1000):\n"
            "        ouverts.append(open('/dev/null', 'rb'))\n"
            "except OSError as exc:\n"
            "    if exc.errno == errno.EMFILE:\n"
            "        print('EMFILE', len(ouverts))\n"
            "    else:\n"
            "        print('AUTRE_ERREUR', exc.errno)\n"
        )
        resultat = self.executer(source, nom="fds_c4.py")

        self.assertIn("EMFILE", resultat)
        self.assertNotIn("AUTRE_ERREUR", resultat)

    # ------------------------------------------------------------------
    # T24 - RLIMIT_NPROC volontairement absent
    # ------------------------------------------------------------------
    def test_T24_rlimit_nproc_non_applique(self):
        capacites = lanceur_python_c4.capacites()
        self.assertNotIn("RLIMIT_NPROC", capacites["limites"])
        self.assertFalse(capacites["nproc"]["applique"])
        self.assertNotIn(
            "RLIMIT_NPROC",
            [nom for nom, _doux, _dur in lanceur_python_c4.LIMITES],
        )

        doux, dur = resource.getrlimit(resource.RLIMIT_NPROC)
        resultat = self.executer(
            "import json, resource\n"
            "print(json.dumps(list(resource.getrlimit(resource.RLIMIT_NPROC))))\n",
            nom="nproc_c4.py",
        )

        self.assertTrue(resultat.startswith("SUCCES"), resultat)
        self.assertIn(json.dumps([doux, dur]), resultat)


class TestProcessusC4(_BaseExecutionC4):
    """Etape 4 : arbre de processus, echeance murale, sorties bornees."""

    @staticmethod
    def _mort(pid):
        """Vrai si le PID n'existe plus ou est un zombie (deja termine)."""
        try:
            with open(f"/proc/{pid}/stat", "rb") as fichier:
                donnees = fichier.read(8192)
        except OSError:
            return True
        fin = donnees.rfind(b")")
        if fin < 0:
            return True
        champs = donnees[fin + 2:].split()
        return not champs or champs[0] in (b"Z", b"X")

    def _attendre_mort(self, pid, delai=5.0):
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            if self._mort(pid):
                return True
            time.sleep(0.05)
        return self._mort(pid)

    # ------------------------------------------------------------------
    # T12 - echeance murale (30 s)
    # ------------------------------------------------------------------
    def test_T12_echeance_murale(self):
        resultat = self.executer(
            "import time\ntime.sleep(60)\n", nom="echeance_c4.py"
        )
        self.assertTrue(
            resultat.startswith("Erreur : delai maximal"), resultat
        )
        self.assertIn("30 secondes", resultat)

    # ------------------------------------------------------------------
    # T13 - enfant et petit-enfant du meme groupe tues
    # ------------------------------------------------------------------
    def test_T13_arbre_du_groupe_tue(self):
        # Le retour d'echeance ne contient pas la sortie : les PID sont
        # ecrits dans le dossier de test, qui survit a l'execution.
        fichier_pids = os.path.join(self.dossier, "arbre_pids.txt")
        source = (
            "import os, subprocess, sys, time\n"
            "a = subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(120)'])\n"
            "b = subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(120)'])\n"
            f"with open({fichier_pids!r}, 'w') as f:\n"
            "    f.write(' '.join(str(p) for p in "
            "(os.getpid(), a.pid, b.pid)))\n"
            "time.sleep(120)\n"
        )
        resultat = self.executer(source, nom="arbre_c4.py")

        with open(fichier_pids, "r", encoding="utf-8") as fichier:
            pids = [int(v) for v in fichier.read().split()]
        self.assertEqual(len(pids), 3, resultat)
        self.assertTrue(
            resultat.startswith("Erreur : delai maximal"), resultat
        )
        for pid in pids:
            self.assertTrue(
                self._attendre_mort(pid),
                f"processus {pid} toujours vivant apres l'echeance",
            )

    # ------------------------------------------------------------------
    # T14 - descendant setsid tue par le chien de garde (marqueur)
    # ------------------------------------------------------------------
    def test_T14_descendant_setsid_marque_tue(self):
        source = (
            "import os, time\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    os.setsid()\n"
            "    time.sleep(120)\n"
            "    os._exit(0)\n"
            "print('FORK', pid, flush=True)\n"
            "time.sleep(0.2)\n"
        )
        resultat = self.executer(source, nom="setsid_c4.py")

        self.assertTrue(resultat.startswith("SUCCES"), resultat)
        morceaux = [
            ligne.split() for ligne in resultat.splitlines()
            if ligne.startswith("FORK ")
        ]
        self.assertEqual(len(morceaux), 1, resultat)
        pid = int(morceaux[0][1])
        self.addCleanup(self._tuer, pid)
        self.assertTrue(
            self._attendre_mort(pid),
            f"descendant setsid {pid} non nettoye par le chien de garde",
        )

    @staticmethod
    def _tuer(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # T15 - tube retenu par un petit-enfant : retour borne
    # ------------------------------------------------------------------
    def test_T15_tube_retenu_ne_bloque_pas(self):
        source = (
            "import os, time\n"
            "pid = os.fork()\n"
            "if pid == 0:\n"
            "    time.sleep(60)\n"
            "    os._exit(0)\n"
            "print('FORK', pid, flush=True)\n"
        )
        debut = time.monotonic()
        resultat = self.executer(source, nom="tube_c4.py")
        duree = time.monotonic() - debut

        morceaux = [
            ligne.split() for ligne in resultat.splitlines()
            if ligne.startswith("FORK ")
        ]
        self.assertEqual(len(morceaux), 1, resultat)
        self.addCleanup(self._tuer, int(morceaux[0][1]))

        self.assertTrue(resultat.startswith("SUCCES"), resultat)
        self.assertIn("code 0", resultat.splitlines()[0])
        self.assertLess(
            duree, 15.0,
            f"retour non borne sur un tube retenu : {duree:.1f} s",
        )

    # ------------------------------------------------------------------
    # T16 - stdout de 10 Mo borne a 64 Ko + drapeau
    # ------------------------------------------------------------------
    def test_T16_stdout_borne(self):
        source = (
            "import sys\n"
            "morceau = 'A' * 8192\n"
            "for _ in range(1300):\n"
            "    sys.stdout.write(morceau)\n"
        )
        resultat = self.executer(source, nom="gros_stdout_c4.py")

        self.assertLessEqual(len(resultat), 70000, len(resultat))
        self.assertIn("tronquee", resultat.lower())

    # ------------------------------------------------------------------
    # T17 - stderr egalement borne
    # ------------------------------------------------------------------
    def test_T17_stderr_borne(self):
        source = (
            "import sys\n"
            "morceau = 'B' * 8192\n"
            "for _ in range(1300):\n"
            "    sys.stderr.write(morceau)\n"
        )
        resultat = self.executer(source, nom="gros_stderr_c4.py")

        self.assertLessEqual(len(resultat), 70000, len(resultat))
        self.assertIn("tronquee", resultat.lower())

    # ------------------------------------------------------------------
    # T18 - contrat verifiers.py : code 0
    # ------------------------------------------------------------------
    def test_T18_contrat_succes_code_zero(self):
        resultat = self.executer("print('bonjour')\n", nom="succes_c4.py")
        premiere = resultat.splitlines()[0]
        self.assertTrue(premiere.startswith("SUCCES :"), resultat)
        self.assertIn("code 0", premiere)
        self.assertIn("bonjour", resultat)

    # ------------------------------------------------------------------
    # T19 - contrat verifiers.py : code non nul + diagnostic
    # ------------------------------------------------------------------
    def test_T19_contrat_echec_code_non_nul(self):
        resultat = self.executer(
            "import sys\nsys.exit(3)\n", nom="echec_c4.py"
        )
        premiere = resultat.splitlines()[0]
        self.assertTrue(premiere.startswith("ECHEC :"), resultat)
        self.assertIn("code 3", premiere)
        self.assertIn("--- diagnostic automatique ---", resultat)


class TestSecretsC4(_BaseExecutionC4):
    """Etape 5 : limite V1, redaction et quarantaine des fuites."""

    # ------------------------------------------------------------------
    # T08 - .env : open() refuse, limite V1 reelle (ctypes)
    # ------------------------------------------------------------------
    def test_T08_env_refuse_puis_contournement_ctypes(self):
        cible = os.path.join(RACINE_PROJET, ".env")
        source = (
            "import ctypes, os\n"
            f"cible = {cible!r}\n"
            "refus = 'REFUS_ECHOUE'\n"
            "try:\n"
            "    open(cible, 'rb').read(1)\n"
            "except PermissionError:\n"
            "    refus = 'REFUS_OK'\n"
            "print(refus)\n"
            "jeton = 'LIMITE_V1_NON_CONFIRMEE'\n"
            "try:\n"
            "    libc = ctypes.CDLL(None, use_errno=True)\n"
            "    fd = libc.open(cible.encode(), os.O_RDONLY)\n"
            "    if fd >= 0:\n"
            "        tampon = ctypes.create_string_buffer(512)\n"
            "        n = libc.read(fd, tampon, 511)\n"
            "        libc.close(fd)\n"
            "        if n > 0:\n"
            "            jeton = 'LIMITE_V1_CONFIRMEE'\n"
            "except Exception:\n"
            "    pass\n"
            "print(jeton)\n"
        )
        resultat = self.executer(source, nom="t08_env.py")

        self.assertIn("REFUS_OK", resultat, resultat)
        self.assertNotIn("REFUS_ECHOUE", resultat, resultat)
        self.assertIn("LIMITE_V1_CONFIRMEE", resultat, resultat)
        # Aucune valeur reelle de .env ne doit revenir dans le resultat.
        for valeur in execution_python._valeurs_secretes():
            self.assertNotIn(valeur, resultat)

    # ------------------------------------------------------------------
    # T37 - secret copie dans espace_travail : detecte et mis en quarantaine
    # ------------------------------------------------------------------
    def test_T37_secret_copie_detecte_et_mis_en_quarantaine(self):
        racine = tempfile.TemporaryDirectory(prefix="c4_quarantaine_")
        self.addCleanup(racine.cleanup)

        fichier = os.path.join(self.dossier, "fuite_secret.txt")
        source = (
            f"with open({fichier!r}, 'w', encoding='utf-8') as f:\n"
            f"    f.write({MARQUEUR!r})\n"
        )

        with patch.object(
            execution_python, "DOSSIER_QUARANTAINE", racine.name
        ), patch.object(
            execution_python, "_valeurs_secretes", return_value=(MARQUEUR,)
        ):
            resultat = self.executer(source, nom="fuite_c4.py")

        self.assertTrue(resultat.startswith("ECHEC"), resultat)
        self.assertIn("secret", resultat.lower(), resultat)
        self.assertNotIn(MARQUEUR, resultat)
        self.assertFalse(os.path.exists(fichier), "copie encore dans espace_travail")

        copies = []
        for dossier, _, noms in os.walk(racine.name):
            for nom in noms:
                copies.append(os.path.join(dossier, nom))
        self.assertEqual(len(copies), 1, copies)

        copie = copies[0]
        self.assertEqual(
            stat.S_IMODE(os.stat(copie).st_mode), 0o600, copie
        )
        self.assertEqual(
            stat.S_IMODE(os.stat(os.path.dirname(copie)).st_mode), 0o700
        )
        with open(copie, "r", encoding="utf-8") as fichier_copie:
            self.assertEqual(fichier_copie.read(), MARQUEUR)


class TestIntegriteC4(_BaseExecutionC4):
    """Etape 5 : l'integrite d'un fichier protege est verifiee, sans restauration."""

    # ------------------------------------------------------------------
    # T37b - modification d'un fichier protege : ECHEC, aucun restore
    # ------------------------------------------------------------------
    def test_T37b_modification_fichier_protege_detectee(self):
        protege = os.path.join(self.dossier, "protege_c4.txt")
        with open(protege, "w", encoding="utf-8") as fichier:
            fichier.write("ORIGINAL")

        source = (
            f"with open({protege!r}, 'w', encoding='utf-8') as f:\n"
            "    f.write('MODIFIE_PAR_LE_PROGRAMME')\n"
        )

        with patch.object(
            execution_python, "FICHIERS_PROTEGES", [protege]
        ), patch.object(
            execution_python, "DOSSIERS_PROTEGES", []
        ), patch.object(
            execution_python, "_valeurs_secretes", return_value=()
        ):
            resultat = self.executer(source, nom="integrite_c4.py")

        self.assertTrue(resultat.startswith("ECHEC"), resultat)
        self.assertIn("integrite", resultat.lower(), resultat)
        # Aucune restauration automatique : le contenu modifie est conserve.
        with open(protege, "r", encoding="utf-8") as fichier:
            self.assertEqual(fichier.read(), "MODIFIE_PAR_LE_PROGRAMME")


# ======================================================================
# Etape 6 (V7) : outils communes des tests hors LLM
# ======================================================================

CLES_ENTREE_HORS_LLM = (
    "outil", "arguments", "statut", "disponible", "autorise",
    "arguments_valides", "execute", "resultat", "verification",
)


def _moteur_isole():
    """AIEngine sans config, sans routeur et sans thread de quotas.

    `__new__` evite `AIEngine.__init__` : aucun acces a config/, aucun
    demarrage de thread `quotas`, donc aucun effet de bord sur data/.
    """
    moteur = AIEngine.__new__(AIEngine)
    moteur._initialiser_contextvars()
    moteur.memory_manager = None
    moteur.logger = None
    moteur.derniers_resultats_outils = []
    moteur.action_engagee = False
    moteur.mode_action = False
    return moteur


def _exiger_point_entree(test):
    """Echoue clairement si l'etape 6 n'est pas encore implementee."""
    if not hasattr(AIEngine, "executer_outil_hors_llm"):
        test.fail(
            "AIEngine.executer_outil_hors_llm absent : l'etape 6 (V7) "
            "n'est pas encore implementee."
        )


def _succes_verifie(entree):
    """Critere unique de succes reel, sans test de sous-chaine."""
    verification = entree.get("verification") or {}
    return (
        entree.get("execute") is True
        and entree.get("statut") == "succes"
        and verification.get("verifie") is True
    )


class _FakeMissionManager:
    """MissionManager en memoire : aucun ecrit dans data/missions.json."""

    def __init__(self):
        self.missions = {}

    def ajouter(self, mission_id, agent, objectif):
        self.missions[mission_id] = {
            "id": mission_id,
            "statut": "en_cours",
            "sous_taches": [
                {
                    "id": "st1",
                    "agent": agent,
                    "objectif": objectif,
                    "statut": "nouvelle",
                    "dependances": [],
                    "resultat": None,
                }
            ],
        }

    def obtenir_mission(self, mission_id):
        return self.missions.get(mission_id)

    def obtenir_sous_taches(self, mission_id):
        return self.missions.get(mission_id, {}).get("sous_taches", [])

    def mettre_a_jour_sous_tache(
        self, mission_id, sous_tache_id, nouveau_statut, resultat=None
    ):
        for sous_tache in self.obtenir_sous_taches(mission_id):
            if sous_tache["id"] == sous_tache_id:
                sous_tache["statut"] = nouveau_statut
                if resultat is not None:
                    sous_tache["resultat"] = resultat

    def mettre_a_jour_statut(self, mission_id, nouveau_statut):
        if mission_id in self.missions:
            self.missions[mission_id]["statut"] = nouveau_statut


class _FakeJarvis:
    """Jarvis factice dont l'ai_engine n'expose qu'une liste.

    C'est exactement la forme utilisee par tests/test_e2e_pipeline.py :
    aucune methode, aucune ContextVar. La production ne doit donc jamais
    appeler une methode sur `jarvis.ai_engine` sans verifier sa presence.
    """

    def __init__(self, reponse):
        self._reponse = reponse
        self.ai_engine = type(
            "obj", (object,), {"derniers_resultats_outils": []}
        )()

    def traiter_commande(self, *args, **kwargs):
        return self._reponse


@contextlib.contextmanager
def _mission_isolee(agent, objectif, reponse):
    """Execute une mission sans data/, sans memory/ et sans LLM."""
    import core.jarvis  # noqa: F401  (rend le patch de classe possible)
    import core.subtask_executor  # noqa: F401
    from core import (
        budget_guard, crystallization, deterministic_actions, learning,
    )

    gestionnaire = _FakeMissionManager()
    gestionnaire.ajouter("mission_c4", agent, objectif)
    jarvis = _FakeJarvis(reponse)
    espion_enregistrement = Mock(return_value=None)

    with contextlib.ExitStack() as pile:
        # `subtask_executor` importe MissionManager au niveau module :
        # la cible du patch est son espace de noms, pas mission_manager.
        pile.enter_context(patch.object(
            core.subtask_executor,
            "MissionManager",
            new=lambda *a, **k: gestionnaire,
        ))
        pile.enter_context(patch(
            "core.jarvis.Jarvis", new=lambda *a, **k: jarvis
        ))
        pile.enter_context(patch(
            "core.ai_router.AIRouter._persister", new=lambda *a, **k: None
        ))
        pile.enter_context(patch.object(
            budget_guard, "reinitialiser_mission", lambda *a, **k: None
        ))
        pile.enter_context(patch.object(
            budget_guard, "autorise_mission", lambda *a, **k: (True, None)
        ))
        pile.enter_context(patch.object(
            budget_guard, "enregistrer_appel_mission", lambda *a, **k: None
        ))
        pile.enter_context(patch.object(
            deterministic_actions, "tenter", lambda *a, **k: None
        ))
        pile.enter_context(patch.object(
            crystallization, "trouver_sequence", lambda *a, **k: None
        ))
        pile.enter_context(patch.object(
            crystallization, "rejouer_sequence", lambda *a, **k: {"ok": False}
        ))
        pile.enter_context(patch.object(
            crystallization, "enregistrer_sequence", espion_enregistrement
        ))
        pile.enter_context(patch.object(
            learning, "conseils_pour", lambda *a, **k: ""
        ))
        pile.enter_context(patch.object(
            learning, "enregistrer_solution", lambda *a, **k: None
        ))
        pile.enter_context(patch.object(
            learning, "enregistrer_echec", lambda *a, **k: None
        ))
        yield gestionnaire, jarvis, espion_enregistrement


class TestFallbackGardeC4(_BaseExecutionC4):
    """Etape 6 : le fallback JSON/code passe par le garde-fou unique."""

    @staticmethod
    def _json(action, parametres):
        return json.dumps({"action": action, "parameters": parametres})

    def _surveiller_e2e(self):
        """Nettoie uniquement les `_e2e_*.py` crees pendant ce test."""
        racine = os.path.join(RACINE_PROJET, "espace_travail")
        avant = set(glob.glob(os.path.join(racine, "_e2e_*.py")))

        def nettoyer():
            for chemin in (
                set(glob.glob(os.path.join(racine, "_e2e_*.py"))) - avant
            ):
                try:
                    os.remove(chemin)
                except OSError:
                    pass

        self.addCleanup(nettoyer)
        return avant

    # ------------------------------------------------------------------
    # T25 - executer_script refuse pour un agent sans permission
    # ------------------------------------------------------------------
    def test_T25_executer_script_refuse_sans_permission(self):
        script = (
            "import os\n"
            "dossier = os.path.dirname(os.path.abspath(__file__))\n"
            "with open(os.path.join(dossier, 't25_c4_pwn.txt'), 'w') as f:\n"
            "    f.write('PWN')\n"
        )
        reponse = self._json("executer_script", {"script": script})
        marqueur = os.path.join(
            RACINE_PROJET, "espace_travail", "t25_c4_pwn.txt"
        )
        self.addCleanup(
            lambda: os.path.exists(marqueur) and os.remove(marqueur)
        )
        self._surveiller_e2e()

        with _mission_isolee(
            "02_designer",
            "Execute un script qui cree le fichier de test T25",
            reponse,
        ) as (gestionnaire, _jarvis, espion):
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        self.assertFalse(resultat.get("ok"), resultat)
        self.assertFalse(
            os.path.exists(marqueur),
            "script execute malgre l'absence de permission",
        )
        self.assertEqual(
            gestionnaire.missions["mission_c4"]["statut"], "bloquee"
        )
        espion.assert_not_called()

    # ------------------------------------------------------------------
    # T26 - outil en Erreur : sous-tache bloquee, pas de faux succes
    # ------------------------------------------------------------------
    def test_T26_outil_en_erreur_ne_produit_pas_de_faux_succes(self):
        cible = os.path.join(self.dossier, "t26_c4_ecrit.txt")
        self.addCleanup(
            lambda: os.path.exists(cible) and os.remove(cible)
        )
        reponse = self._json(
            "ecrire_fichier",
            {"chemin": cible, "contenu": "NE_DOIT_PAS_ETRE_ECRIT"},
        )

        with _mission_isolee(
            "09_securite_ia",
            "Cree le fichier T26 de test",
            reponse,
        ) as (gestionnaire, _jarvis, espion):
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        self.assertFalse(resultat.get("ok"), resultat)
        self.assertFalse(
            os.path.exists(cible),
            "ecriture effectuee hors du garde-fou",
        )
        self.assertEqual(
            gestionnaire.missions["mission_c4"]["statut"], "bloquee"
        )
        self.assertEqual(
            gestionnaire.obtenir_sous_taches("mission_c4")[0]["statut"],
            "bloquee",
        )
        espion.assert_not_called()

    # ------------------------------------------------------------------
    # T27 - argument inconnu refuse avant l'appel de l'outil
    # ------------------------------------------------------------------
    def test_T27_argument_inconnu_refuse_avant_appel(self):
        cible = os.path.join(self.dossier, "t27_c4.txt")
        self.addCleanup(
            lambda: os.path.exists(cible) and os.remove(cible)
        )
        reponse = self._json(
            "ecrire_fichier",
            {"chemin": cible, "contenu": "X", "inconnu_t27": 1},
        )

        with _mission_isolee(
            "01_developpeur",
            "Cree le fichier T27 de test",
            reponse,
        ) as (gestionnaire, _jarvis, espion):
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        self.assertFalse(resultat.get("ok"), resultat)
        self.assertFalse(os.path.exists(cible), "appel effectue malgre l'argument inconnu")
        self.assertEqual(
            gestionnaire.missions["mission_c4"]["statut"], "bloquee"
        )
        espion.assert_not_called()

    # ------------------------------------------------------------------
    # T28 - le script temporaire _e2e_*.py est supprime en finally
    # ------------------------------------------------------------------
    def test_T28_fichier_temporaire_supprime_apres_execution(self):
        script = (
            "import os\n"
            "dossier = os.path.dirname(os.path.abspath(__file__))\n"
            "with open(os.path.join(dossier, 't28_c4_ok.txt'), 'w') as f:\n"
            "    f.write('T28_OK')\n"
        )
        reponse = self._json("executer_script", {"script": script})
        marqueur = os.path.join(
            RACINE_PROJET, "espace_travail", "t28_c4_ok.txt"
        )
        self.addCleanup(
            lambda: os.path.exists(marqueur) and os.remove(marqueur)
        )
        avant = self._surveiller_e2e()

        with _mission_isolee(
            "01_developpeur",
            "Execute un script qui ecrit le fichier T28",
            reponse,
        ) as (gestionnaire, _jarvis, _espion):
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        apres = set(glob.glob(
            os.path.join(RACINE_PROJET, "espace_travail", "_e2e_*.py")
        ))
        self.assertTrue(resultat.get("ok"), resultat)
        self.assertTrue(os.path.exists(marqueur), resultat)
        self.assertEqual(
            apres - avant,
            set(),
            "fichier _e2e_*.py laisse dans espace_travail",
        )

    # ------------------------------------------------------------------
    # T40 - compatibilite avec un ai_engine factice (forme e2e_pipeline)
    # ------------------------------------------------------------------
    def test_T40_moteur_factice_compatible(self):
        cible = os.path.join(self.dossier, "t40_c4_fake.txt")
        self.addCleanup(
            lambda: os.path.exists(cible) and os.remove(cible)
        )
        reponse = self._json(
            "ecrire_fichier", {"chemin": cible, "contenu": "FAKE_OK"}
        )

        with _mission_isolee(
            "01_developpeur",
            "Cree le fichier T40 par fallback JSON",
            reponse,
        ) as (gestionnaire, jarvis, _espion):
            self.assertFalse(
                hasattr(jarvis.ai_engine, "executer_outil_hors_llm"),
                "le faux moteur ne doit exposer aucune methode",
            )
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        self.assertTrue(resultat.get("ok"), resultat)
        self.assertTrue(os.path.exists(cible), resultat)
        with open(cible, "r", encoding="utf-8") as fichier:
            self.assertEqual(fichier.read(), "FAKE_OK")

    # ------------------------------------------------------------------
    # T42b - echec d'execution : aucun _e2e_*.py residuel
    # ------------------------------------------------------------------
    def test_T42_plus_echec_sans_fichier_temporaire(self):
        reponse = self._json(
            "executer_script", {"script": "import sys\nsys.exit(1)\n"}
        )
        avant = self._surveiller_e2e()

        with _mission_isolee(
            "01_developpeur",
            "Execute un script qui echoue (T42)",
            reponse,
        ) as (gestionnaire, _jarvis, espion):
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        apres = set(glob.glob(
            os.path.join(RACINE_PROJET, "espace_travail", "_e2e_*.py")
        ))
        self.assertFalse(resultat.get("ok"), resultat)
        self.assertEqual(
            apres - avant,
            set(),
            "fichier _e2e_*.py laisse apres un echec",
        )
        espion.assert_not_called()

    # ------------------------------------------------------------------
    # T43 - execution refusee pour un agent sans permission
    # ------------------------------------------------------------------
    def test_T43_execution_refusee_pour_agent_sans_permission(self):
        script = os.path.join(self.dossier, "t43_c4_script.py")
        marqueur = os.path.join(self.dossier, "t43_c4_pwn.txt")
        with open(script, "w", encoding="utf-8") as fichier:
            fichier.write(
                "import os\n"
                "dossier = os.path.dirname(os.path.abspath(__file__))\n"
                "with open(os.path.join(dossier, 't43_c4_pwn.txt'), 'w') as f:\n"
                "    f.write('PWN')\n"
            )
        self.addCleanup(
            lambda: os.path.exists(marqueur) and os.remove(marqueur)
        )
        reponse = self._json(
            "executer_programme_python", {"chemin": script}
        )

        with _mission_isolee(
            "09_securite_ia",
            "Execute le programme Python t43",
            reponse,
        ) as (gestionnaire, _jarvis, espion):
            from core.subtask_executor import executer_mission

            resultat = executer_mission("mission_c4", auto_planifier=False)

        self.assertFalse(resultat.get("ok"), resultat)
        self.assertFalse(
            os.path.exists(marqueur),
            "programme execute malgre l'absence de permission",
        )
        self.assertEqual(
            gestionnaire.missions["mission_c4"]["statut"], "bloquee"
        )
        espion.assert_not_called()


class TestPointEntreeC4(unittest.TestCase):
    """Etape 6 : contrat, ContextVar et concurrence du point d'entree."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            dir=os.path.join(RACINE_PROJET, "espace_travail"),
            prefix="c4_entree_",
        )
        self.addCleanup(self.temp.cleanup)
        self.racine = os.path.realpath(self.temp.name)

        for attribut, valeur in (
            ("DOSSIER_AUTORISE", self.racine),
            ("FICHIERS_PROTEGES", [
                os.path.join(self.racine, ".env"),
                os.path.join(self.racine, ".supabase_session.json"),
                os.path.join(self.racine, ".git"),
            ]),
            ("DOSSIERS_PROTEGES", [
                os.path.join(self.racine, "core"),
                os.path.join(self.racine, ".git"),
                os.path.join(self.racine, "memory"),
                os.path.join(self.racine, "data"),
            ]),
        ):
            patcheur = patch.object(tools_fichiers, attribut, valeur)
            patcheur.start()
            self.addCleanup(patcheur.stop)

        with open(
            os.path.join(self.racine, "cible.txt"), "w", encoding="utf-8"
        ) as fichier:
            fichier.write("CONTENU_C4")

    # ------------------------------------------------------------------
    # T39 - contrat de retour complet et succes reel
    # ------------------------------------------------------------------
    def test_T39_contrat_de_retour_complet(self):
        _exiger_point_entree(self)
        moteur = _moteur_isole()

        entree = moteur.executer_outil_hors_llm(
            "lire_fichier",
            {"chemin": "cible.txt"},
            agent="01_developpeur",
            outils_autorises=["lire_fichier"],
        )

        self.assertIsInstance(entree, dict)
        for cle in CLES_ENTREE_HORS_LLM:
            self.assertIn(cle, entree, entree)
        self.assertEqual(entree["resultat"], "CONTENU_C4")
        self.assertIs(entree["execute"], True)
        self.assertEqual(entree["statut"], "succes")
        self.assertIs(entree["verification"]["verifie"], True)
        self.assertTrue(_succes_verifie(entree))

        manquant = moteur.executer_outil_hors_llm(
            "lire_fichier",
            {"chemin": "absent_t39.txt"},
            agent="01_developpeur",
            outils_autorises=["lire_fichier"],
        )
        self.assertTrue(
            str(manquant["resultat"]).startswith("Erreur"), manquant
        )
        self.assertIs(manquant["execute"], True)
        self.assertFalse(_succes_verifie(manquant))
        self.assertIs(manquant["verification"]["verifie"], False)

    # ------------------------------------------------------------------
    # T41 - ContextVar restaurees, resultats precedents preserves
    # ------------------------------------------------------------------
    def test_T41_contextvars_restaurees_et_resultats_preserves(self):
        _exiger_point_entree(self)
        moteur = _moteur_isole()
        moteur.agent_courant = "08_testeur_ia"
        moteur.outils_autorises = ["lire_fichier"]
        moteur.mode_action = True
        moteur._message_utilisateur_courant = "SENTINELLE_T41"

        ancien = {"outil": "ancien", "statut": "succes", "execute": True}
        moteur.derniers_resultats_outils.append(ancien)

        entree = moteur.executer_outil_hors_llm(
            "creer_dossier",
            {"chemin": "dossier_t41"},
            agent="09_securite_ia",
            outils_autorises=["creer_dossier"],
            message_utilisateur="objectif t41",
        )

        # L'agent passe a bien ete applique pendant l'appel (09 refuse).
        self.assertEqual(entree["statut"], "non_autorise", entree)
        self.assertIs(entree["execute"], False)
        self.assertFalse(
            os.path.exists(os.path.join(self.racine, "dossier_t41"))
        )

        # Restauration exacte des ContextVar.
        self.assertEqual(moteur.agent_courant, "08_testeur_ia")
        self.assertEqual(moteur.outils_autorises, ["lire_fichier"])
        self.assertIs(moteur.mode_action, True)
        self.assertEqual(
            moteur._message_utilisateur_courant, "SENTINELLE_T41"
        )

        # La liste n'a pas ete remplacee : ancienne entree + nouvelle.
        resultats = moteur.derniers_resultats_outils
        self.assertEqual(len(resultats), 2, resultats)
        self.assertIs(resultats[0], ancien)
        self.assertEqual(resultats[1]["outil"], "creer_dossier")

    # ------------------------------------------------------------------
    # T42a - exception : entree synthetique, pas de propagation
    # ------------------------------------------------------------------
    def test_T42_exception_retourne_une_entree_synthetique(self):
        _exiger_point_entree(self)
        moteur = _moteur_isole()

        with patch.object(
            moteur, "_executer_outil", side_effect=RuntimeError("boom T42")
        ):
            entree = moteur.executer_outil_hors_llm(
                "lire_fichier",
                {"chemin": "cible.txt"},
                agent="01_developpeur",
                outils_autorises=["lire_fichier"],
            )

        self.assertIsInstance(entree, dict, entree)
        self.assertEqual(entree["statut"], "exception", entree)
        self.assertIs(entree["execute"], False)
        self.assertIs(entree["verification"]["verifie"], False)
        self.assertIn("boom T42", entree["resultat"])

    # ------------------------------------------------------------------
    # T44 - isolation ContextVar entre deux threads
    # ------------------------------------------------------------------
    def test_T44_isolation_entre_threads(self):
        _exiger_point_entree(self)
        moteur = _moteur_isole()
        barriere = threading.Barrier(2)
        resultats = {}
        erreurs = []

        def appeler(nom, outil, agent, autorises):
            try:
                barriere.wait(timeout=10)
                resultats[nom] = moteur.executer_outil_hors_llm(
                    outil,
                    {"chemin": "cible.txt"},
                    agent=agent,
                    outils_autorises=autorises,
                )
                resultats[nom + "_agent_apres"] = moteur.agent_courant
            except BaseException as exc:  # noqa: BLE001 - remonte a l'assert
                erreurs.append((nom, repr(exc)))

        fil_a = threading.Thread(
            target=appeler,
            args=("a", "lire_fichier", "01_developpeur", ["lire_fichier"]),
        )
        fil_b = threading.Thread(
            target=appeler,
            args=("b", "ecrire_fichier", "09_securite_ia", ["ecrire_fichier"]),
        )
        fil_a.start()
        fil_b.start()
        fil_a.join(15)
        fil_b.join(15)

        self.assertEqual(erreurs, [], erreurs)
        self.assertEqual(resultats["a"]["statut"], "succes", resultats)
        self.assertEqual(
            resultats["b"]["statut"], "non_autorise", resultats
        )
        self.assertIsNone(resultats["a_agent_apres"], resultats)
        self.assertIsNone(resultats["b_agent_apres"], resultats)
        # Le contexte principal n'a recu aucun resultat des threads.
        self.assertEqual(len(moteur.derniers_resultats_outils), 0)


class TestContratsV7C4(unittest.TestCase):
    """Etape 6 : liste blanche et garde textuelle du retry conditionne."""

    # ------------------------------------------------------------------
    # T38 - liste blanche coherente et outil inconnu refuse
    # ------------------------------------------------------------------
    def test_T38_liste_blanche_coherente(self):
        from core import subtask_executor

        liste = getattr(subtask_executor, "OUTILS_HORS_LLM", None)
        if liste is None:
            self.fail(
                "subtask_executor.OUTILS_HORS_LLM absent : l'etape 6 "
                "(V7) n'est pas encore implementee."
            )

        self.assertIsInstance(liste, tuple, liste)
        self.assertEqual(len(liste), len(set(liste)), liste)
        for nom in liste:
            self.assertIn(nom, FONCTIONS_DISPONIBLES, nom)
            self.assertIn(nom, TOUS_LES_OUTILS, nom)
            self.assertTrue(outil_connu(nom), nom)

        # Les pseudo-outils ne sont pas des outils du catalogue.
        self.assertNotIn("executer_script", liste)
        self.assertNotIn("executer_script_python", liste)

        _exiger_point_entree(self)
        moteur = _moteur_isole()
        entree = moteur.executer_outil_hors_llm(
            "outil_imaginaire",
            {},
            agent="01_developpeur",
            outils_autorises=["outil_imaginaire"],
        )
        self.assertEqual(entree["statut"], "outil_inconnu", entree)
        self.assertIs(entree["execute"], False)
        self.assertIs(entree["disponible"], False)

    # ------------------------------------------------------------------
    # T45 - le retry conditionne de test_quota_guard.py reste intact
    # ------------------------------------------------------------------
    def test_T45_retry_conditionne_preserve(self):
        chemin = os.path.join(
            RACINE_PROJET, "core", "subtask_executor.py"
        )
        with open(chemin, "r", encoding="utf-8") as fichier:
            source = fichier.read()

        self.assertIn("_reponse_a_code", source)
        self.assertIn("not _reponse_a_code", source)


if __name__ == "__main__":
    unittest.main()
