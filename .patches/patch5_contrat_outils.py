from pathlib import Path
import py_compile
import shutil
import sys


ROOT = Path(".")
AI = ROOT / "core" / "ai_engine.py"
VAL = ROOT / "core" / "validation_manager.py"

AI_BACKUP = ROOT / "core" / "ai_engine.py.sauvegarde_patch5_contrat_outils"
VAL_BACKUP = ROOT / "core" / "validation_manager.py.sauvegarde_patch5_contrat_outils"


def erreur(message):
    print(f"[PATCH 5] ERREUR : {message}")
    sys.exit(1)


def sauvegarder(fichier, backup):
    if backup.exists():
        print(f"[PATCH 5] Sauvegarde existante : {backup}")
        return

    shutil.copy2(fichier, backup)
    print(f"[PATCH 5] Sauvegarde créée : {backup}")


def remplacer_unique(texte, ancien, nouveau, description):
    compteur = texte.count(ancien)

    if compteur != 1:
        erreur(
            f"Bloc '{description}' trouvé {compteur} fois "
            f"(attendu exactement 1)."
        )

    return texte.replace(ancien, nouveau, 1)


def compiler(fichier):
    try:
        py_compile.compile(str(fichier), doraise=True)
    except Exception as exc:
        print(f"[PATCH 5] Compilation échouée : {fichier}")
        print(exc)
        return False

    return True


def patch_deja_applique_ai(texte):
    marqueurs = (
        "PATCH5_CONTRAT_OUTILS_V1",
        "def _normaliser_resultat_outil(",
        "def _enregistrer_resultat_outil(",
    )
    return all(m in texte for m in marqueurs)


def patch_deja_applique_validation(texte):
    return "PATCH5_CONTRAT_OUTILS_V1" in texte


def appliquer_ai():
    texte = AI.read_text(encoding="utf-8")

    if patch_deja_applique_ai(texte):
        print("[PATCH 5] AIEngine : patch déjà appliqué.")
        return False

    # ---------------------------------------------------------
    # 1. _obtenir_outils_autorises
    # ---------------------------------------------------------
    ancien = '''    def _obtenir_outils_autorises(self):
        outils_autorises = getattr(self, "outils_autorises", None)

        if outils_autorises is None:
            return OUTILS

        return [
            outil for outil in OUTILS
            if outil.get("function", {}).get("name") in outils_autorises
        ]
'''

    nouveau = '''    # PATCH5_CONTRAT_OUTILS_V1
    def _obtenir_outils_autorises(self):
        """
        Retourne uniquement les outils explicitement autorisés.

        Contrat de sécurité :
        - None -> aucun outil
        - [] -> aucun outil
        - liste explicite -> uniquement cette liste
        """
        outils_autorises = getattr(self, "outils_autorises", None)

        if not outils_autorises:
            return []

        if not isinstance(outils_autorises, (list, tuple, set)):
            return []

        autorises = set(outils_autorises)

        return [
            outil for outil in OUTILS
            if outil.get("function", {}).get("name") in autorises
        ]

    def _normaliser_resultat_outil(
        self,
        nom_fonction,
        arguments,
        resultat,
        *,
        disponible,
        autorise,
        arguments_valides,
        execute,
        verification=None,
        statut=None,
    ):
        """
        Construit le contrat uniforme d'un résultat d'outil.

        Ce dictionnaire devient la source de vérité pour la validation.
        Le texte de 'resultat' reste destiné à l'explication humaine.
        """
        verification = verification or {
            "verifie": False,
            "details": "Aucune verification effectuee."
        }

        if statut is None:
            if not disponible:
                statut = "outil_inconnu"
            elif not autorise:
                statut = "non_autorise"
            elif not arguments_valides:
                statut = "arguments_invalides"
            elif not execute:
                statut = "echec_execution"
            elif verification.get("verifie") is False:
                statut = "verification_echec"
            else:
                statut = "succes"

        return {
            "outil": nom_fonction,
            "arguments": arguments,
            "statut": statut,
            "disponible": bool(disponible),
            "autorise": bool(autorise),
            "arguments_valides": bool(arguments_valides),
            "execute": bool(execute),
            "resultat": str(resultat),
            "verification": verification,
        }

    def _enregistrer_resultat_outil(self, resultat):
        """
        Enregistre un résultat d'outil sous le contrat Patch 5.
        """
        self.derniers_resultats_outils.append(resultat)
        return resultat
'''

    texte = remplacer_unique(
        texte,
        ancien,
        nouveau,
        "_obtenir_outils_autorises",
    )

    # ---------------------------------------------------------
    # 2. _executer_outil
    # ---------------------------------------------------------
    debut = texte.index("    def _executer_outil(self, nom_fonction, arguments):")
    fin = texte.index(
        "    def _verifier_github_ecrire_fichier(",
        debut,
    )

    ancien_executer = texte[debut:fin]

    nouveau_executer = '''    def _executer_outil(self, nom_fonction, arguments):
        """
        Exécute un outil après contrôle strict du contrat.

        Séquence :
        1. disponibilité ;
        2. autorisation ;
        3. validation des arguments ;
        4. exécution réelle ;
        5. vérification indépendante ;
        6. enregistrement structuré.

        'execute=True' signifie que la fonction de l'outil a réellement
        été appelée. Cela ne signifie pas que l'action a réussi.
        """

        # -----------------------------------------------------
        # Etat 1 : disponibilité
        # -----------------------------------------------------
        outil_disponible = (
            nom_fonction in FONCTIONS_DISPONIBLES
            or nom_fonction in {
                "memoriser_info",
                "rechercher_souvenir",
            }
        )

        if not outil_disponible:
            resultat = f"Erreur outil : outil inconnu : {nom_fonction}."

            entree = self._normaliser_resultat_outil(
                nom_fonction,
                arguments,
                resultat,
                disponible=False,
                autorise=False,
                arguments_valides=False,
                execute=False,
                verification={
                    "verifie": False,
                    "details": "Outil inconnu."
                },
                statut="outil_inconnu",
            )

            self._enregistrer_resultat_outil(entree)
            return resultat

        # -----------------------------------------------------
        # Etat 2 : autorisation
        # -----------------------------------------------------
        outils_autorises = getattr(self, "outils_autorises", None)

        # Deny-by-default :
        # None et [] signifient aucun outil autorisé.
        outil_autorise = (
            isinstance(outils_autorises, (list, tuple, set))
            and nom_fonction in outils_autorises
        )

        if not outil_autorise:
            resultat = (
                f"Erreur : loutil {nom_fonction} "
                "nest pas autorise pour cette execution."
            )

            entree = self._normaliser_resultat_outil(
                nom_fonction,
                arguments,
                resultat,
                disponible=True,
                autorise=False,
                arguments_valides=False,
                execute=False,
                verification={
                    "verifie": False,
                    "details": "Outil non autorise."
                },
                statut="non_autorise",
            )

            self._enregistrer_resultat_outil(entree)
            return resultat

        # -----------------------------------------------------
        # Etat 3 : validation des arguments
        # -----------------------------------------------------
        arguments_valides, erreur_arguments = self._valider_arguments_outil(
            nom_fonction,
            arguments,
        )

        if not arguments_valides:
            resultat = erreur_arguments

            entree = self._normaliser_resultat_outil(
                nom_fonction,
                arguments,
                resultat,
                disponible=True,
                autorise=True,
                arguments_valides=False,
                execute=False,
                verification={
                    "verifie": False,
                    "details": str(erreur_arguments),
                },
                statut="arguments_invalides",
            )

            self._enregistrer_resultat_outil(entree)
            return resultat

        # A partir d'ici, un appel réel peut produire un effet.
        self.action_engagee = True

        # -----------------------------------------------------
        # Etat 4 : exécution réelle
        # -----------------------------------------------------
        execute = False

        try:
            execute = True

            if nom_fonction == "memoriser_info" and self.memory_manager:
                resultat = self.memory_manager.memoriser(
                    arguments.get("categorie"),
                    arguments.get("contenu"),
                )

            elif nom_fonction == "rechercher_souvenir" and self.memory_manager:
                resultat = self.memory_manager.rechercher_souvenir(
                    arguments.get("mot_cle"),
                )

            else:
                fonction = FONCTIONS_DISPONIBLES.get(nom_fonction)

                if fonction is None:
                    resultat = "Erreur outil : outil inconnu."
                else:
                    resultat = fonction(**arguments)

        except Exception as exc:
            resultat = (
                "Erreur outil : exception pendant l'exécution : "
                f"{type(exc).__name__}: {exc}"
            )

        # -----------------------------------------------------
        # Etat 5 : vérification indépendante
        # -----------------------------------------------------
        verification = self._verifier_resultat_outil(
            nom_fonction,
            arguments,
            resultat,
        )

        # -----------------------------------------------------
        # Etat 6 : contrat final
        # -----------------------------------------------------
        if not execute:
            statut = "echec_execution"
        elif isinstance(verification, dict) and verification.get("verifie") is False:
            statut = "verification_echec"
        elif str(resultat).startswith("Erreur"):
            statut = "echec_execution"
        else:
            statut = "succes"

        entree = self._normaliser_resultat_outil(
            nom_fonction,
            arguments,
            resultat,
            disponible=True,
            autorise=True,
            arguments_valides=True,
            execute=execute,
            verification=verification,
            statut=statut,
        )

        self._enregistrer_resultat_outil(entree)

        return resultat

'''

    texte = texte[:debut] + nouveau_executer + texte[fin:]

    AI.write_text(texte, encoding="utf-8")
    return True


def appliquer_validation():
    texte = VAL.read_text(encoding="utf-8")

    if patch_deja_applique_validation(texte):
        print("[PATCH 5] ValidationManager : patch déjà appliqué.")
        return False

    ancien = '''        if resultats_outils:
            echecs = [r for r in resultats_outils if str(r.get("resultat", "")).strip().lower().startswith("erreur")]
            if echecs:
                details = "; ".join(f"{r['outil']}: {r['resultat']}" for r in echecs)
                return self._rejeter(f"Action(s) en echec detectee(s) : {details}", mission_id)
'''

    nouveau = '''        # PATCH5_CONTRAT_OUTILS_V1
        if resultats_outils:
            echecs = [
                r for r in resultats_outils
                if (
                    r.get("statut") in {
                        "outil_inconnu",
                        "non_autorise",
                        "arguments_invalides",
                        "echec_execution",
                    }
                    or r.get("execute") is False
                )
            ]

            # Compatibilite prudente avec les anciens resultats.
            if not echecs:
                echecs = [
                    r for r in resultats_outils
                    if (
                        str(r.get("resultat", ""))
                        .strip()
                        .lower()
                        .startswith("erreur")
                        and "statut" not in r
                    )
                ]

            if echecs:
                details = "; ".join(
                    f"{r.get('outil', 'outil inconnu')}: "
                    f"{r.get('resultat', 'echec inconnu')}"
                    for r in echecs
                )
                return self._rejeter(
                    f"Action(s) en echec detectee(s) : {details}",
                    mission_id,
                )
'''

    texte = remplacer_unique(
        texte,
        ancien,
        nouveau,
        "détection des erreurs d'outils",
    )

    ancien_diag = '''        echecs_action = [
            r for r in resultats_outils
            if str(r.get("resultat", "")).strip().lower().startswith("erreur")
        ]
'''

    nouveau_diag = '''        echecs_action = [
            r for r in resultats_outils
            if (
                r.get("statut") in {
                    "outil_inconnu",
                    "non_autorise",
                    "arguments_invalides",
                    "echec_execution",
                }
                or r.get("execute") is False
            )
        ]

        if not echecs_action:
            echecs_action = [
                r for r in resultats_outils
                if (
                    str(r.get("resultat", ""))
                    .strip()
                    .lower()
                    .startswith("erreur")
                    and "statut" not in r
                )
            ]
'''

    texte = remplacer_unique(
        texte,
        ancien_diag,
        nouveau_diag,
        "diagnostic des erreurs d'action",
    )

    VAL.write_text(texte, encoding="utf-8")
    return True


def main():
    if not AI.exists():
        erreur(f"Fichier introuvable : {AI}")

    if not VAL.exists():
        erreur(f"Fichier introuvable : {VAL}")

    sauvegarder(AI, AI_BACKUP)
    sauvegarder(VAL, VAL_BACKUP)

    original_ai = AI.read_text(encoding="utf-8")
    original_val = VAL.read_text(encoding="utf-8")

    try:
        ai_modifie = appliquer_ai()
        val_modifie = appliquer_validation()

        if ai_modifie or val_modifie:
            print("[PATCH 5] Modifications appliquées.")
        else:
            print("[PATCH 5] Aucun fichier modifié : version déjà installée.")

        # -----------------------------------------------------
        # Compilation
        # -----------------------------------------------------
        if not compiler(AI):
            raise RuntimeError("Compilation de ai_engine.py échouée.")

        if not compiler(VAL):
            raise RuntimeError("Compilation de validation_manager.py échouée.")

        print("[PATCH 5] Compilation Python : OK")

        # -----------------------------------------------------
        # Tests comportementaux
        # -----------------------------------------------------
        sys.path.insert(0, str(ROOT / "core"))

        from ai_engine import AIEngine, OUTILS
        from validation_manager import ValidationManager

        # Objet sans initialiser tout AIEngine.
        engine = AIEngine.__new__(AIEngine)
        engine.derniers_resultats_outils = []
        engine.action_engagee = False
        engine.mode_action = False
        engine.outils_autorises = None

        # Test 1 : None -> aucun outil
        outils = engine._obtenir_outils_autorises()

        if outils != []:
            raise RuntimeError(
                "TEST 1 échoué : None doit produire aucun outil."
            )

        print("[TEST 1] None -> aucun outil : OK")

        # Test 2 : [] -> aucun outil
        engine.outils_autorises = []

        if engine._obtenir_outils_autorises() != []:
            raise RuntimeError(
                "TEST 2 échoué : [] doit produire aucun outil."
            )

        print("[TEST 2] [] -> aucun outil : OK")

        # Test 3 : outil explicitement autorisé
        engine.outils_autorises = ["lister_fichiers"]

        noms = {
            outil["function"]["name"]
            for outil in engine._obtenir_outils_autorises()
        }

        if noms != {"lister_fichiers"}:
            raise RuntimeError(
                f"TEST 3 échoué : outils obtenus = {noms}"
            )

        print("[TEST 3] Autorisation explicite : OK")

        # Test 4 : outil refusé
        engine.derniers_resultats_outils = []
        engine.outils_autorises = []

        resultat = engine._executer_outil(
            "lister_fichiers",
            {},
        )

        if not engine.derniers_resultats_outils:
            raise RuntimeError(
                "TEST 4 échoué : résultat d'outil absent."
            )

        entree = engine.derniers_resultats_outils[-1]

        if entree.get("statut") != "non_autorise":
            raise RuntimeError(
                f"TEST 4 échoué : statut = {entree.get('statut')}"
            )

        if entree.get("execute") is not False:
            raise RuntimeError(
                "TEST 4 échoué : outil non autorisé marqué comme exécuté."
            )

        print("[TEST 4] Outil non autorisé bloqué : OK")

        # Test 5 : arguments invalides
        engine.derniers_resultats_outils = []
        engine.outils_autorises = ["lister_fichiers"]

        resultat = engine._executer_outil(
            "lister_fichiers",
            {"argument_inexistant": True},
        )

        entree = engine.derniers_resultats_outils[-1]

        if entree.get("statut") != "arguments_invalides":
            raise RuntimeError(
                f"TEST 5 échoué : statut = {entree.get('statut')}"
            )

        if entree.get("execute") is not False:
            raise RuntimeError(
                "TEST 5 échoué : arguments invalides marqués comme exécutés."
            )

        print("[TEST 5] Arguments invalides bloqués : OK")

        # Test 6 : succès d'un outil sans effet externe dangereux.
        engine.derniers_resultats_outils = []
        engine.outils_autorises = ["lister_fichiers"]

        resultat = engine._executer_outil(
            "lister_fichiers",
            {"dossier": "."},
        )

        entree = engine.derniers_resultats_outils[-1]

        if entree.get("execute") is not True:
            raise RuntimeError(
                "TEST 6 échoué : outil réellement exécuté non marqué execute=True."
            )

        if "verification" not in entree:
            raise RuntimeError(
                "TEST 6 échoué : vérification absente."
            )

        print("[TEST 6] Exécution réelle + vérification : OK")

        # Test 7 : ValidationManager refuse une exécution en échec.
        class LoggerTest:
            def enregistrer(self, message):
                pass

        validation_manager = ValidationManager(LoggerTest())

        validation = validation_manager.valider(
            "Réponse de test valide",
            resultats_outils=[
                {
                    "outil": "test",
                    "statut": "echec_execution",
                    "execute": True,
                    "resultat": "Erreur outil : test",
                    "verification": {
                        "verifie": False,
                        "details": "échec volontaire",
                    },
                }
            ],
        )

        if validation.get("valide") is not False:
            raise RuntimeError(
                "TEST 7 échoué : échec d'exécution accepté."
            )

        print("[TEST 7] Validation refuse l'échec d'exécution : OK")

        # Test 8 : succès validé
        validation = validation_manager.valider(
            "Réponse de test valide",
            resultats_outils=[
                {
                    "outil": "test",
                    "statut": "succes",
                    "execute": True,
                    "resultat": "OK",
                    "verification": {
                        "verifie": True,
                        "details": "preuve OK",
                    },
                }
            ],
        )

        if validation.get("valide") is not True:
            raise RuntimeError(
                "TEST 8 échoué : succès correctement vérifié refusé."
            )

        print("[TEST 8] Succès vérifié accepté : OK")

        print()
        print("==========================================")
        print("PATCH 5 — CONTRAT OUTILS : OK")
        print("==========================================")
        print(f"AI backup  : {AI_BACKUP}")
        print(f"VAL backup : {VAL_BACKUP}")
        print()
        print("Rollback manuel :")
        print(
            f"cp {AI_BACKUP} {AI}"
        )
        print(
            f"cp {VAL_BACKUP} {VAL}"
        )

    except Exception as exc:
        print()
        print("[PATCH 5] ECHEC — ROLLBACK AUTOMATIQUE")
        print(f"Cause : {exc}")

        AI.write_text(original_ai, encoding="utf-8")
        VAL.write_text(original_val, encoding="utf-8")

        print("[PATCH 5] Fichiers restaurés.")
        sys.exit(1)


if __name__ == "__main__":
    main()
