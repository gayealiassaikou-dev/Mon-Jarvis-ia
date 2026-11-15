import os
import json
import re
import unicodedata
import requests
from dotenv import load_dotenv
from core.ai_router import AIRouter
from core.tools import definir_projet_actif, obtenir_projet_actif, executer_tests_python, executer_programme_python, reparer_syntaxe_python, diagnostiquer_code_python, analyser_erreur_python, corriger_code_python, lire_fichier, ecrire_fichier, creer_parent_manquant_pour_ecriture, supprimer_fichier, supprimer_dossier, lister_fichiers, creer_dossier, rechercher_web, creer_projet, ajouter_tache, lister_projets, lister_taches, terminer_tache, supprimer_tache, supprimer_projet, modifier_statut_projet, github_lister_repos, github_lire_fichier, github_ecrire_fichier, github_creer_repo, lire_etat_projets_taches
from core.music_manager import gerer_musique
from core.outils_telephone import SCHEMAS_TELEPHONE, FONCTIONS_TELEPHONE, verifier_action_telephone
from core.tools_schema import OUTILS, OUTILS_GEMINI, _convertir_outils_gemini, FONCTIONS_DISPONIBLES, OUTILS_LECTURE_SEULE
from core.ai_providers import AIProvidersMixin
from core.verifiers import VerifiersMixin

load_dotenv()



class AIEngine(AIProvidersMixin, VerifiersMixin):
    def __init__(self, memory_manager=None, logger=None):
        self.memory_manager = memory_manager
        self.logger = logger
        self.derniers_resultats_outils = []

        # Indique qu'une action d'outil a déjà été engagée
        # pendant la demande courante.
        self.action_engagee = False

        # Mode action utilisé lorsque l'IA doit obligatoirement
        # sélectionner un outil pour exécuter une action.
        self.mode_action = False

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "ai_providers.json"
        )

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.providers = {
            p["nom"]: p
            for p in config.get("providers", [])
        }

        groq = self.providers.get("groq", {})
        openrouter = self.providers.get("openrouter", {})
        gemini = self.providers.get("gemini", {})
        mistral = self.providers.get("mistral", {})

        self.api_key = os.getenv(groq.get("api_key_env", "GROQ_API_KEY"))
        self.api_key_1 = os.getenv("GROQ_API_KEY_1")
        self.url = groq.get("url")
        self.model = groq.get("model")

        self.openrouter_key = os.getenv(
            openrouter.get("api_key_env", "OPENROUTER_API_KEY")
        )
        self.openrouter_url = openrouter.get("url")
        self.openrouter_model = openrouter.get("model")

        self.gemini_key = os.getenv(
            gemini.get("api_key_env", "GEMINI_API_KEY")
        )
        self.gemini_url = gemini.get("url")

        self.mistral_key = os.getenv(
            mistral.get("api_key_env", "MISTRAL_API_KEY")
        )
        self.mistral_url = mistral.get("url")
        self.mistral_model = mistral.get("model")

        self.router = AIRouter(self, persister_quotas=True)

    def demander(
        self,
        message,
        contexte="",
        historique=None,
        outils_autorises=None,
        mode_action=False,
        message_utilisateur_origine=None,
        on_chunk=None,
    ):
        # Nouvelle demande : aucune action n'est encore engagée.
        self.action_engagee = False
        self.derniers_resultats_outils = []

        ancien_outils_autorises = getattr(
            self,
            "outils_autorises",
            None,
        )
        ancien_mode_action = getattr(
            self,
            "mode_action",
            False,
        )

        self.outils_autorises = outils_autorises
        self.mode_action = bool(mode_action)
        ancien_message = getattr(self, "_message_utilisateur_courant", "")
        self._message_utilisateur_courant = str(
            message if message_utilisateur_origine is None
            else message_utilisateur_origine
        )

        from core import budget_guard
        ok, raison = budget_guard.autorise()
        if not ok:
            if self.logger:
                self.logger.enregistrer(f"[BUDGET] Bloque : {raison}")
            return f"Budget IA epuise pour aujourd'hui : {raison}. Reessaie demain ou augmente JARVIS_MAX_APPELS_JOUR."

        try:
            reponse = self.router.demander(
                message,
                contexte,
                historique,
                on_chunk=on_chunk,
            )
            try:
                budget_guard.enregistrer_appel(
                    tokens_estimes=max(200, (len(str(message)) + len(str(reponse))) // 4)
                )
            except Exception:
                pass
            return reponse
        finally:
            self.outils_autorises = ancien_outils_autorises
            self.mode_action = ancien_mode_action
            self._message_utilisateur_courant = ancien_message

    # PATCH5_CONTRAT_OUTILS_V1
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
            elif verification.get("verifie") is True:
                statut = "succes"
            else:
                statut = "verification_echec"

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

        if self.logger is not None:
            try:
                nom = str(resultat.get("outil", "inconnu"))
                statut = str(resultat.get("statut", "inconnu"))
                lignes = str(resultat.get("resultat", "")).splitlines()
                premiere_ligne = lignes[0][:200] if lignes else ""
                self.logger.enregistrer(
                    f"[Outil] {nom} | {statut} | {premiere_ligne}"
                )
            except Exception:
                pass

        return resultat

    def rejouer_outil_echoue(self, outil, outils_autorises=None):
        """
        Rejoue un outil en echec une seule fois.
        Ne confirme le succes que si le nouveau resultat est verifie.
        Conserve les diagnostics en cas de nouvel echec.
        """
        entree = None

        for resultat in reversed(self.derniers_resultats_outils):
            verification = resultat.get("verification")
            if (
                resultat.get("outil") == outil
                and isinstance(verification, dict)
                and verification.get("verifie") is False
            ):
                entree = resultat
                break

        if entree is None:
            return False

        arguments = entree.get("arguments")
        if not isinstance(arguments, dict):
            return False

        resultat_echec = str(entree.get("resultat", "")).lower()
        autorisations = (
            outils_autorises
            if isinstance(outils_autorises, (list, tuple, set))
            else ()
        )
        parent_manquant = (
            outil == "ecrire_fichier"
            and outil in autorisations
            and entree.get("statut") == "echec_execution"
            and entree.get("autorise") is True
            and entree.get("arguments_valides") is True
            and entree.get("execute") is True
            and "dossier parent de" in resultat_echec
            and "n'existe pas" in resultat_echec
            and isinstance(arguments.get("chemin"), str)
        )

        if parent_manquant:
            creer_parent_manquant_pour_ecriture(arguments["chemin"])

        nombre_avant = len(self.derniers_resultats_outils)
        anciennes_autorisations = getattr(self, "outils_autorises", None)
        self.outils_autorises = outils_autorises

        try:
            self._executer_outil(outil, dict(arguments))
        except Exception:
            return False
        finally:
            self.outils_autorises = anciennes_autorisations

        nouveaux_resultats = self.derniers_resultats_outils[nombre_avant:]
        nouveau = next(
            (
                resultat
                for resultat in reversed(nouveaux_resultats)
                if resultat.get("outil") == outil
                and resultat.get("arguments") == arguments
            ),
            None,
        )

        if not isinstance(nouveau, dict):
            return False

        verification = nouveau.get("verification")
        if (
            nouveau.get("statut") != "succes"
            or not isinstance(verification, dict)
            or verification.get("verifie") is not True
        ):
            return False

        self.derniers_resultats_outils[:] = [
            resultat
            for resultat in self.derniers_resultats_outils
            if resultat is not entree
        ]
        return True

    def _valider_arguments_outil(self, nom_fonction, arguments):
        schema = None

        for entree in OUTILS:
            fonction = entree.get("function", {})
            if fonction.get("name") == nom_fonction:
                schema = fonction.get("parameters", {})
                break

        if schema is None:
            return False, f"Erreur validation : schema introuvable pour loutil '{nom_fonction}'."

        if not isinstance(arguments, dict):
            return False, "Erreur validation : les arguments doivent etre un objet."

        proprietes = schema.get("properties", {}) or {}
        requis = schema.get("required", []) or []

        manquants = [nom for nom in requis if nom not in arguments]
        if manquants:
            return False, (
                "Erreur validation : argument(s) obligatoire(s) manquant(s) : "
                + ", ".join(manquants)
            )

        inconnus = [nom for nom in arguments if nom not in proprietes]
        if inconnus:
            return False, (
                f"Erreur validation : argument(s) non autorise(s) pour {nom_fonction} : "
                + ", ".join(repr(nom) for nom in inconnus)
            )

        types = {
            "string": str,
            "object": dict,
            "array": list,
            "boolean": bool,
            "number": (int, float),
            "integer": int,
        }

        for nom, valeur in arguments.items():
            type_attendu = proprietes[nom].get("type")

            if type_attendu not in types:
                continue

            if type_attendu in ("number", "integer") and isinstance(valeur, bool):
                return False, (
                    f"Erreur validation : l'argument '{nom}' doit etre de type "
                    f"{type_attendu}."
                )

            if not isinstance(valeur, types[type_attendu]):
                return False, (
                    f"Erreur validation : l'argument '{nom}' doit etre de type "
                    f"{type_attendu}."
                )

        for nom, valeur in arguments.items():
            regles = proprietes[nom]

            if "enum" in regles and valeur not in regles["enum"]:
                return False, (
                    f"Erreur validation : l'argument '{nom}' doit etre l'une "
                    f"des valeurs {regles['enum']}."
                )

            if isinstance(valeur, str):
                if "minLength" in regles and len(valeur) < regles["minLength"]:
                    return False, (
                        f"Erreur validation : l'argument '{nom}' doit contenir "
                        f"au moins {regles['minLength']} caracteres."
                    )
                if "maxLength" in regles and len(valeur) > regles["maxLength"]:
                    return False, (
                        f"Erreur validation : l'argument '{nom}' doit contenir "
                        f"au plus {regles['maxLength']} caracteres."
                    )

            if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                if "minimum" in regles and valeur < regles["minimum"]:
                    return False, (
                        f"Erreur validation : l'argument '{nom}' doit etre "
                        f">= {regles['minimum']}."
                    )
                if "maximum" in regles and valeur > regles["maximum"]:
                    return False, (
                        f"Erreur validation : l'argument '{nom}' doit etre "
                        f"<= {regles['maximum']}."
                    )

        return True, None

    def _autorisation_suppression_explicite(self, nom_fonction, arguments):
        """Vérifie que la commande utilisateur nomme l'action et sa cible."""
        message = str(getattr(self, "_message_utilisateur_courant", "") or "")
        message = unicodedata.normalize("NFKD", message.casefold())
        message = "".join(c for c in message if not unicodedata.combining(c))
        message = " ".join(message.split())

        verbe = r"(?:supprime\w*|efface\w*|detru\w*|delete|remove)"
        if not re.search(r"\b" + verbe + r"\b", message):
            return False

        motifs_negation = (
            r"\bne\b.{0,100}\b" + verbe + r"\b",
            r"\bn['’]\s*" + verbe + r"\b",
            r"\b(?:do not|don't|never)\s+" + verbe + r"\b",
            r"\b(?:pas|jamais|plus)\s+" + verbe + r"\b",
        )
        if any(re.search(motif, message) for motif in motifs_negation):
            return False

        if not isinstance(arguments, dict):
            return False

        cle = "chemin" if nom_fonction in {"supprimer_fichier", "supprimer_dossier"} else "nom"
        cible = arguments.get(cle)
        if not isinstance(cible, str) or not cible.strip():
            return False

        cible = cible.strip().replace("\\", "/")
        candidats = [cible]
        if nom_fonction in {"supprimer_fichier", "supprimer_dossier"}:
            candidats.append(os.path.basename(cible))

        generiques = {
            "fichier", "le fichier", "ce fichier", "dossier", "le dossier",
            "ce dossier", "projet", "le projet", "ce projet", "tache",
            "la tache", "cette tache",
        }
        for candidat in candidats:
            candidat = unicodedata.normalize("NFKD", candidat.casefold())
            candidat = "".join(
                c for c in candidat if not unicodedata.combining(c)
            )
            candidat = " ".join(candidat.split())
            if candidat and candidat not in generiques and re.search(
                r"(?<!\w)" + re.escape(candidat) + r"(?!\w)", message
            ):
                return True
        return False

    def _executer_outil(self, nom_fonction, arguments):
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
        # Protection supplémentaire : aucune suppression sans demande explicite.
        outils_destructifs = {
            "supprimer_fichier", "supprimer_dossier", "supprimer_tache", "supprimer_projet"
        }
        if (
            nom_fonction in outils_destructifs
            and not self._autorisation_suppression_explicite(
                nom_fonction, arguments
            )
        ):
            resultat = (
                "Suppression bloquee : la commande doit demander explicitement "
                "la suppression et nommer la cible."
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
                    "details": "Aucune suppression executee : autorisation absente.",
                },
                statut="suppression_non_autorisee",
            )
            self._enregistrer_resultat_outil(entree)
            return resultat

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
        # Les outils en lecture seule n'engagent aucune action.
        if nom_fonction not in OUTILS_LECTURE_SEULE:
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
        elif str(resultat).startswith("Erreur"):
            statut = "echec_execution"
        elif (
            isinstance(verification, dict)
            and verification.get("verifie") is True
        ):
            statut = "succes"
        else:
            statut = "verification_echec"

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

