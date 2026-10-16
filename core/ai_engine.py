import os
import json
import requests
from dotenv import load_dotenv
from core.ai_router import AIRouter
from core.tools import executer_tests_python, lire_fichier, ecrire_fichier, creer_parent_manquant_pour_ecriture, supprimer_fichier, lister_fichiers, creer_dossier, rechercher_web, creer_projet, ajouter_tache, lister_projets, lister_taches, terminer_tache, supprimer_tache, supprimer_projet, modifier_statut_projet, github_lister_repos, github_lire_fichier, github_ecrire_fichier, github_creer_repo, lire_etat_projets_taches

load_dotenv()

OUTILS = [
    {
        "type": "function",
        "function": {
            "name": "lire_fichier",
            "description": "Lit le contenu d'un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a lire"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ecrire_fichier",
            "description": "Ecrit ou remplace un fichier en utilisant un chemin relatif a la racine du depot. Inclure le sous-dossier du projet cible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif depuis la racine du depot, sous-dossier du projet inclus, par exemple Dandé Lenol/saikou/gaye.txt"},
                    "contenu": {"type": "string", "description": "Contenu a ecrire dans le fichier"}
                },
                "required": ["chemin", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_fichier",
            "description": "Supprime definitivement un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a supprimer"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_fichiers",
            "description": "Recherche et liste les fichiers et dossiers du projet. Si le chemin exact est introuvable, examine les chemins proches proposés dans le résultat. Si la cible est un fichier, appelle lire_fichier avec son chemin exact pour lire son contenu. Si la cible est un dossier, appelle lister_fichiers avec le chemin exact pour explorer son contenu. Enchaîne les appels nécessaires au lieu de t’arrêter à une simple suggestion. Ne prétends jamais avoir lu un fichier sans résultat de lecture.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dossier": {"type": "string", "description": "Chemin relatif du dossier a lister, par defaut le dossier racine"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creer_dossier",
            "description": "Cree un dossier avec un chemin relatif a la racine du depot. Inclure le sous-dossier du projet cible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif depuis la racine du depot, sous-dossier du projet inclus si necessaire."}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_creer_repo",
            "description": "Cree un depot GitHub avec l'authentification locale gh et verifie son existence",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {
                        "type": "string",
                        "description": "Nom du nouveau depot GitHub"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description du depot"
                    },
                    "public": {
                        "type": "boolean",
                        "description": "True pour un depot public, False pour un depot prive"
                    }
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_lister_repos",
            "description": "Liste les depots GitHub de l'utilisateur",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_lire_fichier",
            "description": "Lit le contenu d'un fichier depuis un depot GitHub",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Nom complet du depot, format utilisateur/repo"},
                    "chemin": {"type": "string", "description": "Chemin du fichier dans le depot"}
                },
                "required": ["repo", "chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_ecrire_fichier",
            "description": "Cree ou met a jour un fichier dans un depot GitHub avec un commit",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Nom du depot GitHub. Le nom simple du depot est suffisant, par exemple Dande-Lenol. Si seul le nom du depot est fourni, l outil determine automatiquement le compte GitHub authentifie. Le format utilisateur/repo est aussi accepte."},
                    "chemin": {"type": "string", "description": "Chemin du fichier dans le depot"},
                    "contenu": {"type": "string", "description": "Nouveau contenu du fichier"},
                    "message": {"type": "string", "description": "Message du commit"}
                },
                "required": ["repo", "chemin", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memoriser_info",
            "description": "Enregistre une information importante en memoire longue duree pour s en souvenir plus tard",
            "parameters": {
                "type": "object",
                "properties": {
                    "categorie": {"type": "string", "description": "Categorie: projets, decisions, preferences, connaissances ou erreurs"},
                    "contenu": {"type": "string", "description": "L information a memoriser"}
                },
                "required": ["categorie", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_souvenir",
            "description": "Recherche une information precedemment memorisee",
            "parameters": {
                "type": "object",
                "properties": {
                    "mot_cle": {"type": "string", "description": "Mot-cle a rechercher dans la memoire"}
                },
                "required": ["mot_cle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_web",
            "description": "Recherche des informations actuelles sur internet",
            "parameters": {
                "type": "object",
                "properties": {
                    "requete": {"type": "string", "description": "La requete de recherche"}
                },
                "required": ["requete"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creer_projet",
            "description": "Cree un nouveau projet dans le suivi de Jarvis",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet a creer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ajouter_tache",
            "description": "Ajoute une nouvelle tache dans le suivi de Jarvis",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache"},
                    "projet": {"type": "string", "description": "Le projet associe, optionnel"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_projets",
            "description": "Liste tous les projets enregistres",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_taches",
            "description": "Liste toutes les taches enregistrees",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminer_tache",
            "description": "Marque une tache comme terminee",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache a terminer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_tache",
            "description": "Supprime une tache du suivi",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache a supprimer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_projet",
            "description": "Supprime un projet du suivi",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet a supprimer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modifier_statut_projet",
            "description": "Modifie le statut d'un projet (en cours, en pause, termine, annule)",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet"},
                    "nouveau_statut": {"type": "string", "description": "Le nouveau statut : en cours, en pause, termine ou annule"}
                },
                "required": ["nom", "nouveau_statut"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "executer_tests_python",
            "description": "Lance la suite complete des tests Python du depot et retourne les resultats reels, avec un delai maximal de 90 secondes.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

# Outils sans effet de bord : ils n'engagent pas d'action, donc le
# routeur peut essayer un autre fournisseur sans risque de double execution.
OUTILS_LECTURE_SEULE = frozenset({
    "lire_fichier", "lister_fichiers", "lister_projets", "lister_taches",
    "rechercher_web", "rechercher_souvenir",
    "github_lister_repos", "github_lire_fichier",
})

FONCTIONS_DISPONIBLES = {
    "lire_fichier": lire_fichier,
    "ecrire_fichier": ecrire_fichier,
    "supprimer_fichier": supprimer_fichier,
    "lister_fichiers": lister_fichiers,
    "creer_dossier": creer_dossier,
    "github_creer_repo": github_creer_repo,
    "github_lister_repos": github_lister_repos,
    "github_lire_fichier": github_lire_fichier,
    "github_ecrire_fichier": github_ecrire_fichier,
    "rechercher_web": rechercher_web,
    "creer_projet": creer_projet,
    "ajouter_tache": ajouter_tache,
    "lister_projets": lister_projets,
    "lister_taches": lister_taches,
    "terminer_tache": terminer_tache,
    "supprimer_tache": supprimer_tache,
    "supprimer_projet": supprimer_projet,
    "modifier_statut_projet": modifier_statut_projet,
    "executer_tests_python": executer_tests_python
}


def _convertir_outils_gemini(outils):
    declarations = []
    for outil in outils:
        fonction = outil["function"]
        declarations.append({
            "name": fonction["name"],
            "description": fonction["description"],
            "parameters": fonction["parameters"]
        })
    return [{"functionDeclarations": declarations}]


OUTILS_GEMINI = _convertir_outils_gemini(OUTILS)


class AIEngine:
    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
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

        self.router = AIRouter(self)

    def demander(
        self,
        message,
        contexte="",
        historique=None,
        outils_autorises=None,
        mode_action=False,
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

        try:
            return self.router.demander(
                message,
                contexte,
                historique,
            )
        finally:
            self.outils_autorises = ancien_outils_autorises
            self.mode_action = ancien_mode_action

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
                + ", ".join(inconnus)
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

    def _verifier_github_ecrire_fichier(self, arguments, resultat):
        # Relit le fichier sur GitHub et compare exactement au contenu demande.
        import base64
        import json
        import subprocess
        import time

        if isinstance(resultat, str) and resultat.startswith("Erreur"):
            return {"verifie": False, "details": f"L'ecriture GitHub a echoue : {resultat}"}

        repo = arguments.get("repo")
        chemin = arguments.get("chemin")
        contenu = arguments.get("contenu")
        if (not isinstance(repo, str) or not repo.strip()
                or not isinstance(chemin, str) or not chemin.strip()
                or not isinstance(contenu, str)):
            return {"verifie": False, "details": "Verification impossible : repo, chemin ou contenu absent des arguments."}

        repo = repo.strip()
        chemin = chemin.strip()

        try:
            if "/" not in repo:
                p = subprocess.run(["gh", "api", "user", "--jq", ".login"],
                                   capture_output=True, text=True, timeout=15, check=False)
                login = p.stdout.strip()
                if p.returncode != 0 or not login:
                    return {"verifie": False, "details": "Verification impossible : compte GitHub introuvable."}
                repo = f"{login}/{repo}"

            raison = ""
            for tentative in range(2):
                if tentative > 0:
                    time.sleep(2)
                lecture = subprocess.run(["gh", "api", f"repos/{repo}/contents/{chemin}"],
                                         capture_output=True, text=True, timeout=15, check=False)
                if lecture.returncode != 0:
                    raison = "Lecture GitHub echouee : " + (lecture.stderr.strip() or lecture.stdout.strip() or "erreur inconnue")
                    continue
                donnees = json.loads(lecture.stdout)
                if not isinstance(donnees, dict) or donnees.get("type") != "file":
                    return {"verifie": False, "details": "Le chemin n'est pas un fichier sur GitHub."}
                if donnees.get("encoding") != "base64":
                    return {"verifie": False, "details": "Verification impossible : contenu non fourni en base64 (fichier trop gros ?)."}
                distant = base64.b64decode(donnees.get("content", "")).decode("utf-8")
                if distant == contenu:
                    return {"verifie": True, "details": f"Le contenu de {repo}/{chemin} a ete relu sur GitHub et correspond exactement."}
                raison = "Le contenu present sur GitHub differe du contenu demande."
            return {"verifie": False, "details": raison}
        except FileNotFoundError:
            return {"verifie": False, "details": "Verification impossible : GitHub CLI 'gh' introuvable."}
        except subprocess.TimeoutExpired:
            return {"verifie": False, "details": "Verification impossible : lecture GitHub expiree."}
        except ValueError as e:
            return {"verifie": False, "details": f"Reponse GitHub illisible : {type(e).__name__}: {e}"}
        except OSError as e:
            return {"verifie": False, "details": f"Erreur systeme pendant la verification : {type(e).__name__}: {e}"}


    def _verifier_github_creer_repo(self, arguments, resultat):
        """
        Verifie independamment qu'un depot GitHub existe
        avec la visibilite demandee.
        """
        import json
        import subprocess

        if isinstance(resultat, str) and resultat.startswith("Erreur"):
            return {
                "verifie": False,
                "details": f"La creation du depot a echoue : {resultat}"
            }

        nom = arguments.get("nom")
        public = arguments.get("public", True)

        if not isinstance(nom, str) or not nom.strip():
            return {
                "verifie": False,
                "details": "Verification impossible : nom du depot absent."
            }

        if not isinstance(public, bool):
            return {
                "verifie": False,
                "details": "Verification impossible : public doit etre booleen."
            }

        try:
            verification = subprocess.run(
                [
                    "gh",
                    "repo",
                    "view",
                    nom.strip(),
                    "--json",
                    "nameWithOwner,url,isPrivate",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError:
            return {
                "verifie": False,
                "details": "Verification impossible : GitHub CLI 'gh' est introuvable."
            }
        except subprocess.TimeoutExpired:
            return {
                "verifie": False,
                "details": "Verification GitHub expiree."
            }
        except OSError as erreur:
            return {
                "verifie": False,
                "details": (
                    "Erreur systeme pendant la verification GitHub : "
                    f"{type(erreur).__name__}: {erreur}"
                )
            }

        if verification.returncode != 0:
            details = (
                verification.stderr.strip()
                or verification.stdout.strip()
                or "aucun detail fourni"
            )
            return {
                "verifie": False,
                "details": (
                    "Le depot GitHub n'a pas pu etre relu : "
                    f"{details}"
                )
            }

        try:
            depot = json.loads(verification.stdout)
        except json.JSONDecodeError as erreur:
            return {
                "verifie": False,
                "details": (
                    "Reponse GitHub invalide pendant la verification : "
                    f"{erreur}"
                )
            }

        est_prive = depot.get("isPrivate")
        visibilite_attendue = not public

        if est_prive != visibilite_attendue:
            visibilite = "prive" if est_prive else "public"
            attendue = "prive" if not public else "public"
            return {
                "verifie": False,
                "details": (
                    f"Le depot existe mais sa visibilite est {visibilite}; "
                    f"la demande exige {attendue}."
                )
            }

        return {
            "verifie": True,
            "details": (
                "Le depot GitHub a ete relu independamment avec gh et "
                "correspond a la visibilite demandee : "
                f"{depot.get('nameWithOwner', nom)} "
                f"({depot.get('url', 'URL inconnue')})."
            )
        }

    def _verifier_resultat_outil(self, nom_fonction, arguments, resultat):
        """
        Verifie reellement le resultat d'une action executee par un outil.

        Pour l'instant, ecrire_fichier et creer_dossier disposent d'une
        verification specifique.
        Les autres outils restent inchanges jusqu'a leur audit individuel.
        """

        if nom_fonction == "github_ecrire_fichier":
            return self._verifier_github_ecrire_fichier(arguments, resultat)

        if nom_fonction == "github_creer_repo":
            return self._verifier_github_creer_repo(arguments, resultat)

        if nom_fonction == "creer_dossier":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La creation du dossier a echoue : {resultat}"
                }

            chemin = arguments.get("chemin")

            if not chemin:
                return {
                    "verifie": False,
                    "details": "Verification impossible : chemin absent des arguments."
                }

            chemin_reel = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), chemin)))

            if not os.path.exists(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le dossier demande n'existe pas apres sa creation."
                }

            if not os.path.isdir(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le chemin existe apres l'action mais ce n'est pas un dossier."
                }

            return {
                "verifie": True,
                "details": "Le dossier a ete verifie physiquement et existe bien."
            }
        if nom_fonction in {
            "lire_fichier",
            "lister_fichiers",
            "lister_projets",
            "lister_taches",
        }:
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"{nom_fonction} a retourne une erreur : {resultat}",
                }
            if not isinstance(resultat, str):
                return {
                    "verifie": False,
                    "details": (
                        f"{nom_fonction} a retourne un type invalide : "
                        f"{type(resultat).__name__}."
                    ),
                }
            return {
                "verifie": True,
                "details": (
                    f"{nom_fonction} execute avec succes ; "
                    "le resultat respecte le contrat de lecture."
                ),
            }

        if nom_fonction in {
            "github_lire_fichier",
            "github_lister_repos",
            "rechercher_web",
        }:
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": (
                        f"{nom_fonction} a retourne une erreur : "
                        f"{resultat}"
                    ),
                }

            if not isinstance(resultat, str):
                return {
                    "verifie": False,
                    "details": (
                        f"{nom_fonction} a retourne un type invalide : "
                        f"{type(resultat).__name__}."
                    ),
                }

            return {
                "verifie": True,
                "details": (
                    f"{nom_fonction} execute avec succes ; "
                    "le resultat respecte le contrat de lecture externe."
                ),
            }

        if nom_fonction == "supprimer_tache":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de suppression a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom de la tache absent des arguments."
                }

            etat = lire_etat_projets_taches()
            taches = etat.get("taches", [])

            existe = any(
                isinstance(t, dict)
                and t.get("nom", "").strip().lower() == nom.strip().lower()
                for t in taches
            )

            if existe:
                return {
                    "verifie": False,
                    "details": "La tache existe encore apres la suppression."
                }

            return {
                "verifie": True,
                "details": "La tache a ete verifiee et n'existe plus."
            }

        if nom_fonction == "supprimer_projet":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de suppression a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom du projet absent des arguments."
                }

            etat = lire_etat_projets_taches()
            projets = etat.get("projets", [])

            import unicodedata
            from difflib import SequenceMatcher

            def normaliser_nom(valeur):
                texte = unicodedata.normalize("NFKD", str(valeur or "").strip().casefold())
                texte = "".join(c for c in texte if not unicodedata.combining(c))
                return " ".join(texte.split())

            nom_normalise = normaliser_nom(nom)
            noms_existants = [
                p.get("nom", "").strip()
                for p in projets
                if isinstance(p, dict) and isinstance(p.get("nom"), str)
            ]

            existe = any(
                normaliser_nom(nom_existant) == nom_normalise
                for nom_existant in noms_existants
            )

            if existe:
                return {
                    "verifie": False,
                    "details": "Le projet existe encore apres la suppression."
                }

            ressemblances = [
                nom_existant for nom_existant in noms_existants
                if SequenceMatcher(
                    None, nom_normalise, normaliser_nom(nom_existant)
                ).ratio() >= 0.70
            ]

            if ressemblances:
                return {
                    "verifie": False,
                    "details": (
                        "Suppression non confirmee : le nom recherche ne correspond "
                        "pas exactement a un projet supprime. Projet(s) ressemblant(s) "
                        "encore present(s) : " + ", ".join(ressemblances)
                    )
                }

            return {
                "verifie": True,
                "details": "Le projet a ete verifie et n'existe plus."
            }

        if nom_fonction == "ajouter_tache":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'ajout de la tache a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            projet = arguments.get("projet", "")

            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom de la tache absent des arguments."
                }

            etat = lire_etat_projets_taches()
            taches = etat.get("taches", [])

            for tache in taches:
                if not isinstance(tache, dict):
                    continue

                meme_nom = tache.get("nom", "").strip().lower() == nom.strip().lower()
                meme_projet = tache.get("projet", "").strip().lower() == projet.strip().lower()

                if meme_nom and meme_projet:
                    statut = tache.get("statut", "").strip().lower()

                    if statut == "en attente":
                        return {
                            "verifie": True,
                            "details": "La tache a ete relue dans l'etat structure et existe avec le statut 'en attente'."
                        }

                    return {
                        "verifie": False,
                        "details": f"La tache existe mais son statut est '{statut}' au lieu de 'en attente'."
                    }

            return {
                "verifie": False,
                "details": "La tache n'existe pas lors de la verification apres son ajout."
            }

        if nom_fonction == "creer_projet":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La creation du projet a echoue : {resultat}"
                }

            nom = arguments.get("nom")

            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom du projet absent des arguments."
                }

            etat = lire_etat_projets_taches()
            projets = etat.get("projets", [])

            for projet in projets:
                if not isinstance(projet, dict):
                    continue

                if projet.get("nom", "").strip().lower() == nom.strip().lower():
                    statut = projet.get("statut", "").strip().lower()

                    if statut == "en cours":
                        return {
                            "verifie": True,
                            "details": "Le projet a ete relu dans l'etat structure et existe avec le statut 'en cours'."
                        }

                    return {
                        "verifie": False,
                        "details": f"Le projet existe mais son statut est '{statut}' au lieu de 'en cours'."
                    }

            return {
                "verifie": False,
                "details": "Le projet n'existe pas lors de la verification apres sa creation."
            }

        if nom_fonction == "modifier_statut_projet":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"La modification du statut a echoue : {resultat}"
                }

            nom = arguments.get("nom")
            nouveau_statut = arguments.get("nouveau_statut")

            if (
                not isinstance(nom, str) or not nom.strip()
                or not isinstance(nouveau_statut, str) or not nouveau_statut.strip()
            ):
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom ou nouveau statut absent des arguments."
                }

            nom_recherche = nom.strip().lower()
            statut_attendu = nouveau_statut.strip().lower()

            etat = lire_etat_projets_taches()
            projets = etat.get("projets", [])

            for projet in projets:
                if not isinstance(projet, dict):
                    continue

                if projet.get("nom", "").strip().lower() == nom_recherche:
                    statut = projet.get("statut", "").strip().lower()

                    if statut == statut_attendu:
                        return {
                            "verifie": True,
                            "details": "Le projet a ete relu dans l'etat structure et son statut correspond au statut demande."
                        }

                    return {
                        "verifie": False,
                        "details": f"Le projet existe mais son statut est '{statut}' au lieu de '{statut_attendu}'."
                    }

            return {
                "verifie": False,
                "details": "Le projet est introuvable lors de la verification."
            }

        if nom_fonction == "terminer_tache":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de terminaison a echoue : {resultat}"
                }

            nom = arguments.get("nom")

            if not isinstance(nom, str) or not nom.strip():
                return {
                    "verifie": False,
                    "details": "Verification impossible : nom de la tache absent des arguments."
                }

            etat = lire_etat_projets_taches()
            taches = etat.get("taches", [])

            for tache in taches:
                if not isinstance(tache, dict):
                    continue

                if tache.get("nom", "").strip().lower() == nom.strip().lower():
                    statut = tache.get("statut", "").strip().lower()

                    if statut == "terminee":
                        return {
                            "verifie": True,
                            "details": "La tache a ete relue dans l'etat structure et son statut est bien terminee."
                        }

                    return {
                        "verifie": False,
                        "details": f"La tache existe mais son statut est '{statut}' au lieu de 'terminee'."
                    }

            return {
                "verifie": False,
                "details": "La tache est introuvable lors de la verification."
            }

        if nom_fonction == "supprimer_fichier":
            if isinstance(resultat, str) and resultat.startswith("Erreur"):
                return {
                    "verifie": False,
                    "details": f"L'action de suppression a echoue : {resultat}"
                }

            chemin = arguments.get("chemin")

            if not chemin:
                return {
                    "verifie": False,
                    "details": "Verification impossible : chemin absent des arguments."
                }

            chemin_reel = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), chemin)))

            if os.path.exists(chemin_reel):
                return {
                    "verifie": False,
                    "details": "Le fichier existe encore apres la suppression."
                }

            return {
                "verifie": True,
                "details": "Le fichier a ete verifie physiquement et n'existe plus."
            }


        if nom_fonction != "ecrire_fichier":
            return {
                "verifie": None,
                "details": "Aucune verification specifique disponible pour cet outil."
            }

        # Si l'action elle-meme a echoue, inutile de tenter une seconde
        # operation de lecture pour verifier son resultat.
        if isinstance(resultat, str) and resultat.startswith("Erreur"):
            return {
                "verifie": False,
                "details": f"L'action d'ecriture a echoue : {resultat}"
            }

        chemin = arguments.get("chemin")
        contenu_attendu = arguments.get("contenu")

        if not chemin:
            return {
                "verifie": False,
                "details": "Verification impossible : chemin absent des arguments."
            }

        if contenu_attendu is None:
            return {
                "verifie": False,
                "details": "Verification impossible : contenu absent des arguments."
            }

        contenu_lu = lire_fichier(chemin)

        if contenu_lu.startswith("Erreur"):
            return {
                "verifie": False,
                "details": f"Lecture de verification echouee : {contenu_lu}"
            }

        if contenu_lu != contenu_attendu:
            return {
                "verifie": False,
                "details": "Le contenu relu ne correspond pas au contenu demande."
            }

        return {
            "verifie": True,
            "details": "Le fichier a ete relu et son contenu correspond exactement a la demande."
        }

    def _appeler_openai_compatible(
    self,
    url,
    headers,
    model,
    message,
    contexte="",
    historique=None,
    outils=None,
    mode_action=False,
):
        messages = []
        if contexte:
            messages.append({"role": "system", "content": contexte})
        if historique:
            for echange in historique:
                messages.append({"role": "user", "content": echange["question"]})
                messages.append({"role": "assistant", "content": echange["reponse"]})
        messages.append({"role": "user", "content": message})

        # Le mode action force uniquement la premiere selection
        # d'un outil. Apres execution, le modele doit pouvoir
        # produire librement sa reponse finale sans etre force
        # a relancer un outil.
        for iteration in range(5):
            payload = {"model": model, "messages": messages}

            if outils:
                payload["tools"] = outils

                if mode_action and iteration == 0:
                    payload["tool_choice"] = "required"
            reponse = requests.post(url, headers=headers, json=payload, timeout=30)
            try:
                reponse.raise_for_status()
            except requests.HTTPError as erreur_http:
                statut = getattr(reponse, "status_code", "inconnu")
                try:
                    details = json.dumps(reponse.json(), ensure_ascii=False)
                except Exception:
                    details = getattr(reponse, "text", "") or str(erreur_http)
                details = str(details)[:1000]
                raise requests.HTTPError(
                    f"HTTP {statut}: {details}",
                    response=reponse,
                ) from erreur_http
            data = reponse.json()
            choix = data["choices"][0]["message"]

            if choix.get("tool_calls"):
                messages.append(choix)
                for appel in choix["tool_calls"]:
                    nom_fonction = appel["function"]["name"]

                    try:
                        arguments = json.loads(
                            appel["function"].get("arguments", "{}")
                        ) or {}

                    except json.JSONDecodeError as e:
                        resultat = (
                            "Erreur outil : arguments JSON invalides : "
                            f"{e}"
                        )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": appel["id"],
                            "content": str(resultat)
                        })

                        continue

                    except (TypeError, AttributeError) as e:
                        resultat = (
                            "Erreur outil : arguments de Tool Calling "
                            f"invalides : {type(e).__name__}: {e}"
                        )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": appel["id"],
                            "content": str(resultat)
                        })

                        continue

                    resultat = self._executer_outil(
                        nom_fonction,
                        arguments
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": appel["id"],
                        "content": str(resultat)
                    })
            else:
                contenu = choix.get("content")

                # Reponse vide sans aucune action engagee : on leve une
                # erreur pour que le routeur essaie le fournisseur suivant.
                # Si une action a deja ete engagee, on garde le comportement
                # actuel : ni rejeu ni fallback (anti-double-execution).
                if (
                    not isinstance(contenu, str) or not contenu.strip()
                ) and not getattr(self, "action_engagee", False):
                    raise Exception(
                        "Reponse vide du fournisseur "
                        "(content absent ou vide)."
                    )

                return contenu

        raise Exception("Trop d'appels d'outils enchaines.")

    def _demander_groq(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.url,
            headers,
            self.model,
            message,
            contexte,
            historique,
            outils=self._obtenir_outils_autorises(),
            mode_action=self.mode_action,
        )
    def _demander_openrouter(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.openrouter_url,
            headers,
            self.openrouter_model,
            message,
            contexte,
            historique,
            outils=self._obtenir_outils_autorises(),
            mode_action=self.mode_action,
        )
    def _demander_mistral(self, message, contexte="", historique=None):
        headers = {
            "Authorization": f"Bearer {self.mistral_key}",
            "Content-Type": "application/json"
        }
        return self._appeler_openai_compatible(
            self.mistral_url,
            headers,
            self.mistral_model,
            message,
            contexte,
            historique,
            outils=self._obtenir_outils_autorises(),
            mode_action=self.mode_action,
        )

    def _demander_gemini(self, message, contexte="", historique=None):
        contents = []

        if historique:
            for echange in historique:
                contents.append({"role": "user", "parts": [{"text": echange["question"]}]})
                contents.append({"role": "model", "parts": [{"text": echange["reponse"]}]})

        contents.append({"role": "user", "parts": [{"text": message}]})

        payload = {"contents": contents, "tools": _convertir_outils_gemini(self._obtenir_outils_autorises())}
        if contexte:
            payload["systemInstruction"] = {"parts": [{"text": contexte}]}

        url = self.gemini_url + "?key=" + self.gemini_key

        for _ in range(5):
            reponse = requests.post(url, json=payload, timeout=30)
            reponse.raise_for_status()
            data = reponse.json()
            candidat = data["candidates"][0]["content"]

            appels_fonction = [p["functionCall"] for p in candidat.get("parts", []) if "functionCall" in p]

            if appels_fonction:
                contents.append(candidat)
                parts_resultats = []
                for appel in appels_fonction:
                    nom_fonction = appel["name"]
                    arguments = appel.get("args", {}) or {}
                    resultat = self._executer_outil(nom_fonction, arguments)
                    parts_resultats.append({
                        "functionResponse": {
                            "name": nom_fonction,
                            "response": {"resultat": str(resultat)}
                        }
                    })
                contents.append({"role": "user", "parts": parts_resultats})
                payload["contents"] = contents
            else:
                textes = [p.get("text", "") for p in candidat.get("parts", [])]
                return "".join(textes)

        raise Exception("Trop d'appels d'outils enchaines (Gemini).")
