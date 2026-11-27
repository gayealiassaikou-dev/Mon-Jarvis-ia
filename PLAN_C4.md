# PLAN C4 — Confinement de l'exécution Python

Statut : plan proposé, **aucun code modifié**, en attente de validation.
Périmètre : `executer_programme_python` (V1–V6), `subtask_executor.py` (V7), `crystallization.py` (V8).
Environnement cible : Termux + proot-distro Ubuntu, aarch64, Python 3.14.10 (mesuré).

Rappel de numérotation (alignée sur l'audit C4 V1→V8) :
V1 lecture de secrets par le code exécuté ; V2 écriture/contournement de chemins (TOCTOU, lien dur) ;
V3 réseau libre ; V4 timeouts qui ne tuent que l'enfant direct ; V5 sortie non bornée ; V6 ressources
non limitées ; V7 fallback LLM de `subtask_executor` hors garde-fou + faux succès ; V8 rejeu de
cristallisation hors garde-fou + séquences périmées/empoisonnées.

Décision structurante : **il n'existe aucun bac à sable fiable dans cet environnement**. C4 ne peut donc
pas « fermer » V1/V2 au sens confidentialité/intégrité. C4 applique ce qui est réellement applicable
(limites noyau, seccomp réseau, arbre de processus, sortie bornée, environnement filtré, garde-fou
central réutilisé) et **documente explicitement** ce qui reste ouvert. Aucun `eval` filtré, AST filtré
ou `RestrictedPython` ne sera présenté comme une sandbox.

## 1. Protections réellement disponibles (mesuré, pas supposé)

| Mécanisme | État mesuré | Verdict C4 |
|---|---|---|
| `unshare -Ur` | rc=0 mais `uid=0` factice et `CapEff=0` : aucun user namespace réel | inutilisable |
| `unshare -p` / `-m` / `-n` | PID partagé (`ps` voit 16 processus) ; `connect()` vers 1.1.1.1:443 réussit ; un `mount --bind` reste visible après sortie (fuite globale) | inutilisable |
| `bwrap` | absent (dépend des user namespaces) | inutilisable |
| `firejail` | absent (setuid + namespaces + capabilities) | inutilisable |
| proot imbriqué (`proot -r /`) | se bloque (`statut t`), tué après 15 s | fragile, inutilisable |
| seccomp | filtre Android déjà actif (`Seccomp: 2`, `NoNewPrivs: 1`) ; `prctl(PR_SET_SECCOMP)` renvoie 0 et bloque réellement `mkdirat(34)` et `socket(198)` en EPERM | **utilisable partiellement** |
| seccomp — cas piégeux | filtre sur `getpid(172)` installé sans effet observable | chaque règle doit être prouvée par un test |
| Landlock | `landlock_create_ruleset` → `ENOSYS` (38) | inutilisable (pas de contrôle par chemin) |
| cgroups v1/v2 | `/sys/fs/cgroup` : Permission denied | inutilisable |
| `ulimit`/`setrlimit` | `RLIMIT_CPU` tue (SIGXCPU, rc 152) ; `RLIMIT_FSIZE` → EFBIG ; `RLIMIT_AS` → MemoryError ; `RLIMIT_NOFILE` → EMFILE | **utilisable** |
| `RLIMIT_NPROC` | avec limite 40, le premier `fork` échoue déjà (compteur global de l'UID Android) | à ne jamais utiliser |
| utilisateur dédié / capabilities | `uid=0` factice, `CapEff=0` ; le noyau voit toujours l'UID de l'app Termux | cosmétique, inutilisable |
| `setsid`, `timeout`, `prlimit` | présents (`/usr/bin`) | utilisable pour l'arbre de processus |
| Android `isolatedProcess` / app séparée / VM | seule vraie frontière, hors périmètre du dépôt | hors C4 |

Conséquences : proot n'est **pas** un outil de sécurité (traduction de chemins par ptrace) ; les
namespaces sont émulés ; seccomp ne filtre pas les chemins ; aucun mécanisme ne peut restreindre un
processus à `espace_travail/`. Le seul contrôle par chemin reste celui du code Python (contournable).

## 2. Confinement de l'exécution Python : bloqué vs non bloqué

Profil unique `proot-degrade-v1`, appliqué dans un lanceur enfant avant le code utilisateur.

Bloqué (garanti par le noyau ou par le parent) :
- création de sockets `AF_INET`, `AF_INET6`, `AF_PACKET`, `AF_NETLINK`, `AF_VSOCK` ;
- `execve`/`execveat` : plus aucun binaire externe (`/bin/sh`, `python`, `git`) après le démarrage ;
- `ptrace`, `process_vm_readv/writev`, `open_by_handle_at`, `name_to_handle_at` ;
- `mount`, `umount2`, `pivot_root`, `chroot`, `setns`, `unshare`, `keyctl`, `add_key`, `bpf`,
  `perf_event_open`, `userfaultfd`, `io_uring_setup`, `reboot`, `init_module`, `delete_module`,
  `swapon/off`, `sethostname`, `settimeofday`, `clock_settime`, `kill` (les threads utilisent `tgkill`) ;
- limites : CPU, mémoire virtuelle, taille par fichier, descripteurs, core dumps, mur d'horloge ;
- volume de `stdout`/`stderr` (plafonné et signalé) ;
- variables d'environnement hors liste blanche (donc aucun secret d'environnement) ;
- imports hors stdlib et hors dossier du script (`-I`, ni `PYTHONPATH` ni `sitecustomize`).

Non bloqué (assumé, voir (d)) :
- lecture de tout fichier lisible par l'app : `.env`, `memory/`, `data/`, `core/`, `/sdcard`, `$HOME` ;
- écriture/suppression hors `espace_travail/` (projet, `/sdcard`) ;
- copie d'un secret vers `espace_travail/` puis lecture par l'outil `lire_fichier` ;
- descendants `fork` sans `exec` qui font `setsid` (nettoyés au mieux, pas garantis) ;
- quota disque global (seule la taille par fichier est bornée) ;
- exfiltration par la sortie du programme vers le LLM (les secrets lus peuvent être imprimés).

Un hook d'audit Python et une redaction de sortie seront ajoutés comme **cloche avertisseuse**, jamais
comme barrière : contournables par `ctypes`/syscalls directs, et ils ne changent pas la table ci-dessus.

## 3. Contrôle accès fichiers (V1, V2)

Deux couches, à ne pas confondre.

Couche outils (`tools_fichiers.py`, réellement applicable) :
- aujourd'hui : validation par `realpath` puis `open`/`remove` → fenêtre TOCTOU (échange de lien
  symbolique entre contrôle et opération) ; aucun contrôle des **liens durs** (un lien dur vers `.env`
  créé dans `espace_travail/` passe `_fichier_protege` et livre le secret à `lire_fichier`).
- cible : ouvrir d'abord avec `O_NOFOLLOW|O_CLOEXEC`, valider ensuite le descripteur (`fstat` +
  `/proc/self/fd/N`), puis lire/écrire via le fd ; pour l'écriture, `O_TRUNC` seulement après
  validation (`ftruncate`) ; suppression et création via `dir_fd` (`unlink`/`mkdir` relatifs au
  dossier parent ouvert en `O_DIRECTORY|O_NOFOLLOW`) ; refus des fichiers dont l'inode correspond à un
  fichier protégé (`st_nlink > 1` → vérification d'inode, coût nul dans le cas courant).
- messages et préfixes inchangés (`Erreur :`, `accès refusé`) pour ne pas casser C3 ni les appelants.

Couche exécution (V1, non fermable) :
- le parent transmet au lanceur la politique de chemins (racine projet, liste protégée) ; le hook
  d'audit refuse `open` en lecture sur les chemins protégés et en écriture hors `espace_travail/` ;
- après exécution : contrôle d'intégrité (taille/mtime, hash si < 5 Mo) des fichiers protégés, et
  recherche des valeurs secrètes connues (lues depuis `.env` par le parent) dans les fichiers
  nouvellement créés de `espace_travail/` ; en cas de détection → résultat en échec, fichier
  quarantaine/supprimé, aucune restauration automatique ;
- redaction des valeurs secrètes (exactes, base64, hex) dans `stdout`/`stderr` avant retour au LLM.
- Limite explicite : ces mesures sont de la **détection**, pas du confinement. Un code adversarial
  garde la confidentialité et l'intégrité. La seule correction réelle est hors C4 (app séparée/VM).

## 4. Réseau (V3)

Mesuré : sans filtre, un programme du `espace_travail` atteint 1.1.1.1:443 ; `capture_output` renvoie
la sortie au LLM (canal d'exfiltration indirect même sans socket).

Contrôle retenu : filtre seccomp `proot-degrade-v1` installé par le lanceur, avant le code utilisateur.
- `socket(domain, …)` : refus si `domain` ∈ {2 (INET), 10 (INET6), 17 (PACKET), 16 (NETLINK), 40 (VSOCK)} ;
  autoriser `AF_UNIX` (asyncio/socketpair) — risque local résiduel documenté ;
- refus de `connect` et `sendto` (défense en profondeur : plus aucun envoi, même si un fd traînait) ;
- `close_fds=True`, `stdin=DEVNULL`, aucun `pass_fds` : aucun socket hérité ;
- environnement : liste blanche (ni proxy, ni token) ;
- preuve obligatoire par test : `socket(AF_INET)` et `urllib` échouent en EPERM, pas seulement « le
  test passe ». Chaque numéro de syscall est figé dans une table aarch64 et vérifié par un test dédié.
- Limites : seccomp ne voit pas les chemins (pas de filtrage par destination) ; un bug de fuite de fd
  rouvrirait la voie ; les sockets `AF_UNIX` locales (Termux:API, adb) restent accessibles si autorisées.

## 5. Processus secondaires et ressources (V4, V5, V6)

Mesuré sur `subprocess.run(timeout=2)` : `TimeoutExpired` à 2 s mais **3 petits-enfants `setsid`
survivent** (PPID 1) et une variante bloque la capture au-delà de 45 s. `run(timeout=)` tue l'enfant
direct puis rappelle `communicate()`, qui attend l'EOF d'un tube encore tenu par un descendant.

Conception (V4) :
- `Popen(..., start_new_session=True, close_fds=True)` → le script est chef de session/groupe ;
- drains `stdout`/`stderr` bornés (threads ou `selectors`), jamais de `communicate()` sans borne ;
- échéance murale (30 s par défaut) : `SIGTERM` au groupe, grâce 2 s, puis `SIGKILL` au groupe, puis
  `wait(timeout)` borné et fermeture explicite des tubes ; le résultat conserve le préfixe
  `Erreur : delai maximal …` (contrat `verifiers.py`) ;
- marqueur `JARVIS_EXEC_ID` dans l'environnement + chien de garde parent qui scanne `/proc/*/environ`
  (toutes les 0,5 s et une fois après sortie) pour tuer les descendants échappés par `setsid` ;
- les descendants qui ont `setsid` **et** `execve` sont impossibles (execve bloqué) ; un clone Python
  échappé reste possible → nettoyage au mieux, pas de garantie.

Conception (V5) : plafond 64 Ko conservés par flux, drapeau « sortie tronquée », au-delà de 4 Mo
cumulés → arrêt du programme. Mémoire du parent bornée par construction ; le test vérifie la longueur
et le drapeau, pas la RSS.

Conception (V6), dans l'ordre du lanceur :
`RLIMIT_CORE=0`, `RLIMIT_NOFILE=64`, `RLIMIT_FSIZE=8 Mo`, `RLIMIT_AS=512 Mo`, `RLIMIT_CPU=20 s` (hard 25).
`RLIMIT_NPROC` **interdit** (mesure : bloque tout l'UID Android). `HOME`/`TMPDIR`/`XDG_*` dans un
dossier par exécution sous `espace_travail/.exec_<id>/`, supprimé en `finally`.
`executer_tests_python()` reçoit la même échéance (le message promet 90 s mais aucun `timeout=` n'est
passé aujourd'hui) ; il reste hors seccomp (code du dépôt, pas du LLM).
Limites : quota disque global absent ; `RLIMIT_CPU` est par processus (le mur d'horloge borne l'ensemble) ;
`RLIMIT_AS` peut faire échouer numpy/torch — assumé et documenté.

## 6. Fermeture V7 (`subtask_executor.py`) et V8 (`crystallization.py`)

### V7 — plus aucun outil hors garde-fou, plus de faux succès
Constats : le fallback JSON/`executer_script` appelle `mapping[nom](**params)` en direct (aucun
`verifier_execution`, permissions d'agent ignorées), passe `**params` non validés, force
`est_echec=False` dès qu'un outil est appelé même si le résultat est `Erreur`, puis enregistre
`statut="succes", execute=True` en dur — ce qui empoisonne V8. Fichiers `_e2e_*.py`/`sous_tache_*.py`
non nettoyés (8 déjà présents dans `espace_travail/`).

Correctifs :
- nouveau point d'entrée unique `AIEngine.executer_outil_hors_llm(nom, args, agent, outils_autorises)`
  qui pose les `ContextVar` (tokens + `finally`, invariant C2), appelle `_executer_outil` (garde-fou,
  validation d'arguments, `verifiers.py`, enregistrement) puis restaure le contexte ;
- `subtask_executor` n'importe plus `core.tools` pour le fallback : il construit une liste blanche
  explicite, valide `inspect.signature` (clés inconnues refusées), puis appelle le point d'entrée ;
- succès = entrée enregistrée avec `execute is True` **et** `statut == "succes"` **et**
  `verification["verifie"] is True`. Sinon `bloquee` avec la raison exacte ;
- `executer_script` = deux étapes explicites et gardées (écriture puis exécution), code plafonné à
  20 Ko, fichier temporaire supprimé en `finally` ;
- suppression des `except Exception: pass` du chemin fallback (journalisation + refus explicite) ;
- vérifier d'abord que `chercher_opportunites` figure au catalogue `tool_guard` ; sinon le retirer de
  la liste blanche (refus explicite) plutôt que de contourner le garde-fou.
- Inchangé : chemin déterministe, pipeline LLM principal, `max_etapes`, budget, signatures publiques.

### V8 — rejeu gardé, borné, idempotent et versionné
Constats : `rejouer_sequence` exécute des séquences stockées sans agent ni permissions, sans schéma
d'arguments, avec un succès détecté par sous-chaîne dans les 50 premiers caractères ; une séquence
`ecrire_fichier` périmée écrase du contenu plus récent ; `_signature` approximative (≥ 50 % de mots)
peut rejouer la mauvaise séquence ; `rechercher_web` est rejouable (coût + effet réseau).

Correctifs :
- métadonnées de séquence : `version`, `agent`, `empreinte` (sha256), `date`, `derniere_utilisation` ;
  les entrées sans `version` sont ignorées (retour au LLM), pas d'erreur ;
- avant **toute** exécution : validation globale (≤ 20 étapes, outils ∈ liste rejouable, args dict,
  tailles, `inspect.signature`) puis pré-contrôle de toutes les étapes via `verifier_execution` ;
  une seule étape refusée ⇒ zéro exécution (pas de rejeu partiel) ;
- exécution via `executer_outil_hors_llm` ; `ok` seulement si **toutes** les étapes sont vérifiées ;
- détection d'échec sur toute la chaîne de résultat (`Erreur`, `ECHEC`, `échec`), pas sur 50 caractères ;
- idempotence : pour `ecrire_fichier`, refus si le fichier existe avec un hash différent de celui
  enregistré ; pour `executer_programme_python`, refus si le hash du script a changé ; hash enregistré
  au moment du succès ;
- `enregistrer_sequence` n'accepte que les entrées vérifiées (`verification.verifie is True`) et
  horodate ; `rechercher_web` retiré des outils rejouables (à valider) ;
- `_charger`/`_sauvegarder` protégés par un verrou (lecture-modification-écriture atomique via fichier
  temporaire + `os.replace`) : pas d'état mutable partagé entre requêtes (C2) ;
- `trouver_sequence` exige un agent compatible ; la correspondance partielle reste mais ne peut plus
  contourner le garde-fou.

## 7. Invariants C1/C2/C3 à préserver

| Invariant | Règle opposable pendant C4 | Vérification |
|---|---|---|
| C1 — accès web | aucune route, aucun écouteur, aucun cookie modifié ; le mot de passe web n'entre jamais dans l'environnement enfant (liste blanche) | `tests/test_web_auth.py` inchangé, vert |
| C2 — garde-fou unique | tout outil passe par `verifier_execution` (deny-by-default, permissions d'agent) ; aucun contournement par fallback, cristallisation ou rejeu | `test_tool_guard.py`, `test_deterministic_securite.py` inchangés + tests C4 |
| C2 — concurrence | aucun état mutable global nouveau ; `ContextVar` posés/restaurés par token (`finally`) ; verrou pour `crystallized.json` | `test_concurrence_c2_1.py` inchangé + test de rejeu concurrent |
| C2 — vérité du résultat | `execute=True` ≠ succès ; succès seulement si `verification["verifie"]` | tests V7/V8 |
| C3 — secrets | `_fichier_protege` reste la source unique (`memory/`, `data/`, `backups/`, `.patches/`, `interface/data/`, `.env*`, `.supabase_session*`, `ai_providers.json*`, `core/`, `.git`) ; aucun contenu sensible dans un résultat d'outil | `test_protection_secrets_c3.py` inchangé, vert |
| C3 — accès direct légitime | les modules internes (mémoire, missions, Supabase) continuent d'écrire directement leurs fichiers : ne pas les router vers les outils | revue de diff + tests existants |

Règles de non-régression : aucune modification des listes C3 (uniquement durcissement du même
périmètre), aucune modification de la sémantique de `verifier_execution`, aucun nouvel endpoint,
aucune nouvelle dépendance, messages d'erreur existants conservés.

## 8. Tests `tests/test_execution_python_c4.py`

Tous offline (aucun `@llm`, aucune clé API), exécutés avec le `conftest.py` existant. Les scripts de
test sont créés dans un dossier temporaire sous `espace_travail/` et supprimés ; jamais de
`rmtree("espace_travail")`.

| # | Cas | Prouve | Ne prouve pas |
|---|---|---|---|
| T01 | profil `proot-degrade-v1` rapporté explicitement (`capacites()` : landlock absent, namespaces factices, seccomp partiel) | le code annonce ses garanties réelles | qu'un mécanisme noyau isole quoi que ce soit |
| T02 | script hors `espace_travail` refusé | le contrôle de chemin d'entrée reste actif | qu'un script autorisé ne lise pas hors zone |
| T03 | script via lien symbolique refusé | `realpath` + politique d'entrée | l'absence de TOCTOU (voir T35) |
| T04 | script protégé (`core/`, `memory/`) refusé | réutilisation de `_fichier_protege` | la lecture directe par code Python |
| T05 | extension non `.py` refusée | le contrat d'entrée | rien sur le contenu |
| T06 | variables `*TOKEN*`, `*KEY*`, `PYTHONPATH`, `LD_PRELOAD` absentes de l'enfant | liste blanche d'environnement effective | que les secrets des fichiers soient inaccessibles |
| T07 | `import core` échoue dans l'enfant (`-I`, sans `PYTHONPATH`) | pas d'injection par `PYTHONPATH`/`sitecustomize` | l'import par chemin absolu / `importlib` |
| T08 | `.env` lisible par le programme exécuté (**test de limite assumée**) | la limite V1 est réelle et suivie | qu'on puisse la fermer ici ; si ce test casse, mettre à jour (d) |
| T09 | `socket(AF_INET)` → `EPERM` | seccomp réseau actif | qu'aucun autre canal (AF_UNIX, sortie LLM) n'existe |
| T10 | `urllib` vers `127.0.0.1` échoue | blocage applicatif réel | le filtrage par destination (impossible en BPF) |
| T11 | aucun fd hérité visible dans l'enfant | `close_fds`, `stdin=DEVNULL` | les fuites futures si `pass_fds` est ajouté |
| T12 | `sleep(60)` → échéance ~30 s, retour `Erreur : delai maximal` | le mur d'horloge et le contrat `verifiers` | l'arrêt de l'arbre (voir T13) |
| T13 | enfant + petit-enfant même groupe tués | `killpg` couvre le groupe | les descendants `setsid` (voir T14) |
| T14 | descendant `setsid` tué par le chien de garde (marqueur) | nettoyage au mieux | l'absence de course / de PID réutilisé |
| T15 | petit-enfant qui garde le tube : retour borné (régression du blocage mesuré) | plus de `communicate()` non borné après kill | la propreté des tubes côté noyau |
| T16 | `stdout` de 10 Mo → résultat ≤ 64 Ko + « tronquée » | capture bornée | la RSS pendant le drain |
| T17 | `stderr` également borné | symétrie des deux flux | rien de plus |
| T18 | code 0 → première ligne `SUCCES : … code 0` | contrat conservé avec `verifiers.py` | la véracité métier du script |
| T19 | code ≠ 0 → `ECHEC :` + diagnostic | contrat conservé | l'exactitude du diagnostic |
| T20 | `RLIMIT_FSIZE` : écriture 10 Mo → EFBIG/SIGXFSZ, fichier ≤ 8 Mo | plafond par fichier | quota disque global |
| T21 | `RLIMIT_AS` : allocation 2 Go → MemoryError/échec propre | plafond mémoire | RSS/swap réels |
| T22 | boucle CPU infinie → tuée (SIGXCPU ou mur) | plafond CPU | cumul sur l'arbre |
| T23 | 1000 ouvertures → EMFILE | plafond descripteurs | fuites du parent |
| T24 | profil ne pose pas `RLIMIT_NPROC` | garde contre la régression mesurée (UID entier) | l'absence de fork bomb (assumé) |
| T25 | fallback `executer_script` refusé pour un agent sans permission, aucun fichier créé | V7 : garde-fou réutilisé | les autres chemins du LLM |
| T26 | outil renvoie `Erreur` → sous-tâche `bloquee`, aucune séquence enregistrée | fin du faux succès | le comportement d'un vrai LLM |
| T27 | argument inconnu dans le JSON → refus avant appel | validation de signature | les abus d'arguments valides |
| T28 | fichier `_e2e_*.py` supprimé après exécution | hygiène disque | les plantages hors `finally` |
| T29 | rejeu V8 par `09_securite_ia` → refus, fichier intact | permissions appliquées au rejeu | les modifications hors outils |
| T30 | séquence [autorisée, interdite] → zéro étape exécutée | pré-contrôle global (atomicité d'autorisation) | un changement de permissions en cours de rejeu |
| T31 | `ecrire_fichier` rejoué sur contenu divergent → refus | idempotence (pas d'écrasement silencieux) | la détection si contenu identique |
| T32 | séquence non vérifiée non enregistrée ; entrée sans `version` ignorée | anti-empoisonnement + migration douce | l'édition manuelle du JSON |
| T33 | résultat contenant « échec » après le 50e caractère → échec détecté | détection sur toute la chaîne | la vérification sémantique |
| T34 | séquence de 50 étapes → refus | borne de rejeu | les séquences longues légitimes |
| T35 | course TOCTOU : lien échangé entre contrôle et ouverture → opération refusée | ouverture par fd + `O_NOFOLLOW` + `fstat` | une course noyau parfaite sur tous les FS |
| T36 | lien dur vers `.env` dans `espace_travail` → `lire_fichier` refuse | contrôle d'inode (`st_nlink`) | la lecture directe par code exécuté |
| T37 | après exécution, secret copié dans `espace_travail` détecté et retiré | détection/réparation au mieux | un encodage exotique / un faux négatif |

Non-régression à exécuter à chaque étape (hors fichier C4) : `test_web_auth.py`, `test_tool_guard.py`,
`test_concurrence_c2_1.py`, `test_deterministic_securite.py`, `test_protection_secrets_c3.py`,
`test_e2e_pipeline.py`, `test_espace_travail_double.py`, `test_deterministic_offline.py`.

## 9. Conclusion opérationnelle

### (a) Fichiers à modifier, un par un

| Fichier | Nature | Justification (une ligne) |
|---|---|---|
| `core/execution_python.py` | modifié | Orchestration V1–V6 : profil, environnement filtré, échéance et drains bornés, contrôle d'intégrité, redaction, nettoyage `finally`. |
| `core/lanceur_python_c4.py` | **nouveau** | Lanceur enfant stdlib-only qui applique `proot-degrade-v1` (rlimits puis seccomp puis hook d'audit) avant le code utilisateur. |
| `core/tools_python.py` | modifié | Passer l'échéance à `executer_tests_python()` (le message promet 90 s) et conserver le wrapper d'entrée existant. |
| `core/tools_fichiers.py` | modifié | Couche outils V1/V2 : ouverture par descripteur (`O_NOFOLLOW`, `fstat`, `dir_fd`) et refus des liens durs vers un fichier protégé. |
| `core/ai_engine.py` | modifié | Ajouter `executer_outil_hors_llm()` comme point d'entrée unique gardé (tokens `ContextVar` posés puis restaurés). |
| `core/subtask_executor.py` | modifié | V7 : fallback sur liste blanche via ce point d'entrée, succès seulement si vérifié, aucun faux succès, nettoyage des fichiers temporaires. |
| `core/crystallization.py` | modifié | V8 : `version`/`agent`/`empreinte`, pré-contrôle global, idempotence, verrou et écriture atomique (`os.replace`). |
| `tests/test_execution_python_c4.py` | **nouveau** | Implémente T01–T37 (offline, aucun `@llm`, aucun `rmtree("espace_travail")`). |
| `PLAN_C4.md` | modifié | Passage du statut « plan proposé » à l'état d'avancement réel, à la clôture uniquement. |

Fichiers **non modifiés**, par invariant §7 : `core/tool_guard.py`, `core/verifiers.py`,
`core/agent_permissions.py`, tout `interface/**`, ainsi que les tests C1/C2/C3 existants. Constat
préalable : `chercher_opportunites` est déjà connu (`TOUS_LES_OUTILS` + `tools_schema.FONCTIONS_DISPONIBLES`),
donc il reste dans la liste blanche V7 sans toucher au garde-fou.

### (b) Ordre d'implémentation

1. **Couche outils fichiers (V1/V2, indépendant).** Modifier `core/tools_fichiers.py` seul ; ajouter
   dans `tests/test_execution_python_c4.py` la section fichiers (T35, T36). Aucun autre fichier touché.
2. **Lanceur enfant : profil, `-I`, environnement, rlimits (V1, V6).** Créer `core/lanceur_python_c4.py`
   et brancher `core/execution_python.py` dessus sans encore changer l'arbre de processus ; tests T01,
   T02–T07, T20–T24.
3. **Seccomp réseau et hygiène des descripteurs (V3).** Ajouter le filtre `proot-degrade-v1` au lanceur,
   `close_fds`/`stdin=DEVNULL` côté parent ; tests T09, T10, T11 (chaque numéro de syscall aarch64 figé
   et vérifié).
4. **Arbre de processus, échéance, sorties bornées (V4, V5).** `start_new_session=True`, drains bornés,
   `SIGTERM`→grâce→`SIGKILL` au groupe, chien de garde `JARVIS_EXEC_ID`, plafonds 64 Ko/4 Mo ; et
   `executer_tests_python()` avec échéance. Tests T12–T19.
5. **Intégrité, quarantaine, redaction (V1, détection).** Contrôle taille/mtime/hash des fichiers
   protégés et recherche des valeurs secrètes dans les nouveaux fichiers de `espace_travail`,
   redaction `stdout`/`stderr`. Tests T08 (limite assumée) et T37.
6. **V7 — point d'entrée unique hors LLM.** D'abord `core/ai_engine.py`, puis `core/subtask_executor.py`
   (liste blanche, `inspect.signature`, succès réel, `finally`) ; tests T25–T28.
7. **V8 — rejeu gardé et idempotent.** `core/crystallization.py` seul (version, pré-contrôle global,
   détection d'échec sur toute la chaîne, hash d'idempotence, verrou, `os.replace`) ; tests T29–T34.
8. **Clôture.** Suite complète verte, mise à jour du statut dans `PLAN_C4.md` ; aucun correctif
   fonctionnel dans cette étape.

### (c) Points de validation avant chaque étape

Baseline commune (une fois, avant l'étape 1) : `git status --short` doit montrer uniquement
`PLAN_C4.md` et les fichiers de données préexistants (`data/missions.json`, `data/missions_archive.json`,
`data/apprentissages.json`, `data/budget_journalier.json`, `memory/memory_index.db`) ; la suite de
non-régression du §8 doit être verte avant toute modification.

1. **Avant l'étape 1** : baseline ci-dessus verte. Après l'étape 1 : `git status --short` n'ajoute que
   `core/tools_fichiers.py` (modifié) et `tests/test_execution_python_c4.py` (nouveau) ;
   `test_protection_secrets_c3.py` et `test_tool_guard.py` verts ; T35/T36 verts.
2. **Avant l'étape 2** : `python -m pytest tests/test_execution_python_c4.py -q` vert pour la section
   fichiers ; `git diff` ne contient aucune modification de `core/tool_guard.py` ni de `core/verifiers.py`.
   Après : `git status --short` n'ajoute que `core/lanceur_python_c4.py` (nouveau) et
   `core/execution_python.py` (modifié), le fichier de tests évoluant ; T01–T07 et T20–T24 verts.
3. **Avant l'étape 3** : le lanceur s'exécute et les rlimits sont mesurées (T20–T24 verts). Après :
   diff limité au lanceur et au fichier de tests ; T09–T11 verts et aucun test existant cassé ; vérifier
   dans le diff qu'aucun `pass_fds` n'apparaît.
4. **Avant l'étape 4** : T09–T11 verts (le réseau reste bloqué après les modifications de process).
   Après : diff limité à `core/execution_python.py`, `core/tools_python.py`, lanceur si nécessaire et
   tests ; T12–T19 verts, dont T15 (non-blocage sur tube retenu) et T18/T19 (contrat `verifiers.py`).
5. **Avant l'étape 5** : T12–T19 verts ; le diff ne touche toujours pas `verifiers.py`. Après : diff
   limité à `core/execution_python.py` + tests ; T08 et T37 verts ; relancer T02–T05 (contrôle d'entrée
   non régressé) et `test_protection_secrets_c3.py`.
6. **Avant l'étape 6** : les 5 premières étapes vertes et `git diff --stat` sans fichier de la couche
   V7/V8. Après : diff limité à `core/ai_engine.py`, `core/subtask_executor.py` et tests ; T25–T28 verts,
   `test_tool_guard.py` et `test_deterministic_securite.py` verts ; vérifier qu'aucun `except Exception: pass`
   ne subsiste dans le chemin fallback (`git diff` le montre supprimé).
7. **Avant l'étape 7** : T25–T28 verts ; aucune modification de `core/agent_permissions.py` dans le diff.
   Après : diff limité à `core/crystallization.py` + tests ; T29–T34 verts, `test_concurrence_c2_1.py` vert
   (verrou) et `data/crystallized.json` non modifié par les tests hors écriture attendue.
8. **Avant l'étape 8** : T01–T37 verts et diff limité aux 7 fichiers de code + le fichier de tests.
   Après : suite complète du §8 verte ; hors baseline, `git status --short` ne contient que les fichiers
   listés en (a) ;
   aucun diff sur `interface/**`, `core/tool_guard.py`, `core/verifiers.py`, `core/agent_permissions.py`,
   ni sur les tests C1/C2/C3.

### (d) Limites résiduelles assumées (regroupées de §2/§3/§4/§5)

- **Confidentialité (V1)** : le code exécuté lit tout fichier lisible par l'app (`.env`, `memory/`,
  `data/`, `core/`, `/sdcard`, `$HOME`) ; un secret copié dans `espace_travail/` reste lisible par
  `lire_fichier` ; un secret lu peut être imprimé et renvoyé au LLM. Le hook d'audit et la redaction
  sont une cloche avertisseuse, contournable par `ctypes`/syscalls directs.
- **Intégrité (V2)** : écriture et suppression hors `espace_travail/` (projet, `/sdcard`) restent
  possibles depuis le code exécuté ; les correctifs `O_NOFOLLOW`/`fstat`/`dir_fd`/inode ne protègent
  que les opérations passées par les outils, pas un accès direct ; aucun confinement par chemin noyau
  (Landlock `ENOSYS`, namespaces émulés).
- **Réseau (V3)** : seccomp bloque domains/`connect`/`sendto` mais ne voit pas la destination ; les
  sockets `AF_UNIX` locales (Termux:API, adb) restent accessibles si autorisées ; toute fuite de
  descripteur rouvrirait un canal ; la sortie du programme reste un canal d'exfiltration indirect.
- **Processus et ressources (V4, V5, V6)** : un descendant `fork` + `setsid` échappé n'est nettoyé
  qu'au mieux (chien de garde, course et réutilisation de PID possibles) ; pas de quota disque global
  (seule la taille par fichier est bornée) ; `RLIMIT_CPU` est par processus (le mur d'horloge borne
  l'ensemble) ; `RLIMIT_NPROC` est inutilisable (bloque tout l'UID Android) ; `RLIMIT_AS` peut faire
  échouer numpy/torch.
- **Portée générale** : C4 ne ferme ni V1 ni V2 — ces mesures sont de la **détection** et du
  durcissement, pas du confinement ; la seule correction réelle reste une app Android séparée ou une
  VM, hors périmètre du dépôt.
