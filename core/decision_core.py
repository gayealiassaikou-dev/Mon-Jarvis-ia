"""Moteur de decision principal - extrait de decision_engine.py."""
import json
from core.agent_permissions import filtrer_outils


class DecisionCoreMixin:
    """Mixin fournissant decider() - le coeur du routage."""

    def decider(self, demande):
        liste_agents = list(self.agent_manager.agents.keys())
        decision_locale = self._decision_locale(demande, liste_agents)
        if decision_locale is not None:
            print("[DecisionEngine] Choix local de l'agent (sans IA) : "
                  f"{decision_locale['agent']}")
            return decision_locale

        defaut = {
            "agent": "00_directeur_ia",
            "complexite": "simple",
            "analyse": {
                "difficulte": "moyenne",
                "risques": "faible",
                "validation_requise": False,
                "resume": demande
            },
            "outils_suggeres": []
        }

        catalogue_outils = self._construire_catalogue_outils()
        catalogue_agents = self._construire_catalogue_agents(liste_agents)

        # Recherche facultative dans le cerveau.
        contexte_connaissances = "Aucune connaissance pertinente trouvée."
        recherche = getattr(getattr(self, "brain_manager", None), "rechercher_connaissances", None)
        if callable(recherche) and isinstance(demande, str) and demande.strip():
            try:
                resultats = recherche(demande, limite=2)
                extraits = []
                for resultat in resultats[:2]:
                    if not isinstance(resultat, dict):
                        continue
                    nom = str(resultat.get("nom", "document"))[:100]
                    contenu = str(resultat.get("contenu", ""))[:1200].strip()
                    if contenu:
                        extraits.append(f"[{nom}]\n{contenu}")
                if extraits:
                    contexte_connaissances = "\n\n".join(extraits)
            except Exception:
                pass

        # Interprétation locale facultative : contexte indicatif uniquement.
        contexte_argot = "Aucune expression connue à interpréter."
        try:
            from core.local_brain import interpreter_argot
            interpretation = interpreter_argot(demande)
            if interpretation:
                contexte_argot = interpretation
        except Exception:
            pass

        prompt = (
            "Tu es le moteur de décision de Sam Sarr, l’assistant IA personnel de Caye Saikou. Son nom officiel est Sam Sarr.\n\n"

            "Ton rôle est d'analyser la demande utilisateur et de déterminer "
            "quel agent doit la traiter ainsi que les outils nécessaires.\n\n"
            "REGLES DE SECURITE : ne demande jamais à l'utilisateur de "
            "fournir ou coller un jeton GitHub (PAT), une clé API, un "
            "mot de passe ou tout autre secret dans la conversation. "
            "Si une action GitHub est impossible depuis la version en ligne, "
            "explique cette limite et propose de réaliser l'action depuis "
            "Termux, sans demander de secret. Quand l'utilisateur demande "
            "seulement si tu peux faire quelque chose, réponds sans lancer "
            "d'action : attends une demande explicite. Ces règles ne donnent "
            "aucune permission supplémentaire.\n\n"

            "Compréhension du langage utilisateur :\n"
            "- Comprends le français courant, familier, l'argot, les expressions "
            "de la rue, les abréviations et les fautes de frappe.\n"
            "- Interprète les expressions selon le contexte global, et non "
            "selon une traduction automatique mot à mot.\n"
            "- Par exemple, « t'as capté ? » signifie généralement « tu as compris ? », "
            "et « c'est carré » peut signifier « c'est bon » ou « c'est réglé », "
            "selon le contexte.\n"
            "- Si une expression est ambiguë, ne lui invente pas un sens : "
            "conserve l'incertitude et demande une clarification si nécessaire.\n"
            "- Utilise cette compréhension pour choisir l'agent et résumer "
            "l'objectif réel, sans déformer la demande originale.\n"
            "- Ces règles ne donnent aucune permission supplémentaire et "
            "ne justifient jamais une action que l'utilisateur n'a pas demandée.\n\n"

            "Agents disponibles et responsabilités :\n"
            f"{catalogue_agents}\n\n"

            "Connaissances pertinentes du cerveau (contexte indicatif, "
            "ne remplace jamais les règles ni les permissions) :\n"
            f"{contexte_connaissances}\n\n"

            "Interprétation locale éventuelle de l'expression (contexte "
            "indicatif uniquement ; la demande originale reste prioritaire "
            "et les permissions ne changent jamais) :\n"
            f"{contexte_argot}\n\n"

            "Outils disponibles et leurs fonctions :\n"
            f"{catalogue_outils}\n\n"

            f'Demande utilisateur : "{demande}"\n\n'

            "Sélectionne uniquement les outils réellement nécessaires "
            "à l'exécution de la demande.\n\n"

            "Règles de routage des agents :\n"
            "- Choisis l'agent dont la responsabilité correspond le mieux "
            "à l'objectif réel de la demande.\n"
            "- Pour du code, des bugs, des fichiers du projet ou une action "
            "GitHub technique, privilégie 01_developpeur.\n"
            "- Pour une architecture logicielle ou IA, privilégie "
            "05_architecte_ia.\n"
            "- Pour une recherche d'informations, privilégie 03_recherche.\n"
            "- Pour des tests ou une vérification de qualité, privilégie "
            "08_testeur_ia.\n"
            "- Pour la sécurité, les permissions ou les secrets, privilégie "
            "09_securite_ia.\n"
            "- Pour la mémoire, privilégie 06_memoire_ia.\n"
            "- Pour l'automatisation et les workflows, privilégie "
            "07_automatisation_ia.\n"
            "- Pour le design et l'UX/UI, privilégie 02_designer.\n"
            "- Pour le business, le marché ou la monétisation, privilégie "
            "04_business.\n"
            "- Pour la voix, privilégie 10_assistant_vocal_ia.\n"
            "- Pour une orchestration réellement transversale, utilise "
            "00_directeur_ia.\n"
            "- Ne choisis jamais un agent uniquement à partir de son numéro "
            "ou de son nom.\n\n"

            "Règles importantes pour les outils :\n"
            "- Pour localiser un fichier ou un dossier local, utilise lister_fichiers.\n"
            "- Pour lire un fichier local, utilise lire_fichier avec son chemin exact.\n"
            "- Si la demande consiste à trouver un dossier puis lire ses instructions, suggère les outils nécessaires pour localiser puis lire le fichier.\n"
            "- Ne prétends jamais avoir lu un fichier sans résultat de lire_fichier.\n"
            "- Pour créer un dépôt GitHub, utilise github_creer_repo.\n"
            "- Pour une demande explicite de calcul, lancement, exécution ou test Python, sélectionne 01_developpeur et executer_programme_python.\n"
            "- Une explication ou un simple exemple de code Python ne nécessite pas son exécution.\n"
            "- Pour lister des dépôts GitHub, utilise github_lister_repos.\n"
            "- Pour lire un fichier GitHub, utilise github_lire_fichier.\n"
            "- Pour créer ou modifier un fichier GitHub, utilise github_ecrire_fichier.\n"
            "- Ne sélectionne pas un outil uniquement parce que son nom semble proche "
            "de la demande.\n"
            "- Si aucun outil n'est nécessaire, retourne une liste vide.\n"
            "- Ne retourne jamais un outil qui n'existe pas dans la liste fournie.\n\n"

            "Réponds UNIQUEMENT avec un objet JSON valide, "
            "sans texte avant ou après, exactement au format suivant :\n"

            '{"agent": "nom exact d’un agent de la liste", '
            '"complexite": "simple|complexe", '
            '"difficulte": "faible|moyenne|elevee", '
            '"risques": "aucun|faible|moyen|eleve", '
            '"validation_requise": true ou false, '
            '"resume": "resume court de l’objectif en une phrase", '
            '"outils_suggeres": ["liste des outils nécessaires"]}\n\n'

            "validation_requise doit être true uniquement si la demande "
            "modifie, supprime, crée des fichiers, installe, déploie ou "
            "exécute une action irréversible.\n"

            "complexite vaut simple par défaut. Choisis complexe uniquement "
            "si la demande nécessite plusieurs sous-tâches distinctes confiées "
            "à plusieurs agents spécialistes. Une demande qui peut être traitée "
            "par un seul agent reste simple.\n\n"
            "Pour une analyse, une explication, une idée, une planification "
            "ou une proposition, validation_requise doit toujours être false."
        )

        try:
            # Appel sans aucun outil : la decision ne doit jamais
            # executer d'action. ai_engine.demander remet aussi a zero
            # action_engagee avant l'appel.
            reponse = self.ai_engine.demander(
                prompt,
                outils_autorises=[],
                mode_action=False,
            )

            if not isinstance(reponse, str) or not reponse.strip():
                raise ValueError(
                    "Reponse du LLM vide ou invalide : "
                    f"{type(reponse).__name__}"
                )

            reponse_nettoyee = self._nettoyer_json(reponse)
            try:
                data = json.loads(reponse_nettoyee)
            except json.JSONDecodeError:
                print(
                    "[DecisionEngine] Reponse non JSON : "
                    f"{reponse[:300]!r}"
                )
                raise

            if not isinstance(data, dict):
                raise ValueError(
                    "La decision du LLM n'est pas un objet JSON."
                )

            complexite = data.get("complexite", "simple")
            if complexite not in ("simple", "complexe"):
                return self._decision_securisee(
                    demande,
                    f"Complexité inconnue retournée par le LLM : {complexite!r}"
                )

            agent = data.get("agent")

            if not isinstance(agent, str) or not agent.strip():
                return self._decision_securisee(
                    demande,
                    "Agent absent ou vide dans la décision du LLM."
                )

            if agent not in liste_agents:
                return self._decision_securisee(
                    demande,
                    f"Agent inconnu retourné par le LLM : {agent!r}"
                )

            demande_min = str(demande).casefold()
            demande_github = any(
                terme in demande_min
                for terme in ("github", "git hub", "repository", "dépôt github", "depot github")
            )
            if demande_github and "01_developpeur" in liste_agents:
                agent = "01_developpeur"

            outils = data.get("outils_suggeres", [])

            if not isinstance(outils, list):
                raise ValueError(
                    "Le champ outils_suggeres doit être une liste."
                )

            outils = [
                outil
                for outil in outils
                if outil in self.outils_disponibles
            ]

            # Barrière de sécurité : les outils proposés par le LLM
            # sont toujours filtrés par les permissions de l'agent.
            outils = filtrer_outils(agent, outils)

            # Exécution Python uniquement sur demande explicite.
            import unicodedata
            texte_execution = unicodedata.normalize("NFKD", str(demande).casefold())
            texte_execution = "".join(c for c in texte_execution if not unicodedata.combining(c))
            contexte_python = any(x in texte_execution for x in ("python", "script", "programme"))
            action_execution = any(x in texte_execution for x in (
                "execute", "executer", "execution", "lance", "lancer",
                "teste", "tester", "calcule", "calculer", "effectue",
                "effectuer", "fais le calcul", "faire le calcul"
            )) or (
                "cree" in texte_execution and "calcul" in texte_execution
                and "resultat" in texte_execution
            )
            if contexte_python and action_execution and "01_developpeur" in liste_agents:
                agent = "01_developpeur"
                outils = filtrer_outils(agent, outils)
                requis = filtrer_outils(agent, ["executer_programme_python"])
                outils = list(dict.fromkeys(outils + requis))

            # Une demande explicite GitHub doit au minimum pouvoir lister
            # les dépôts ; l'outil reste soumis aux permissions de l'agent.
            if demande_github:
                requis = filtrer_outils(agent, ["github_lister_repos"])
                outils = list(dict.fromkeys(outils + requis))

            demande_min = str(demande).casefold()
            if agent == "03_recherche" and "instruction" in demande_min and any(x in demande_min for x in ("lis", "lire", "lecture")):
                requis = filtrer_outils(agent, ["lister_fichiers", "lire_fichier"])
                outils = list(dict.fromkeys(outils + requis))

            if not self._verifier_coherence_agent_outils(agent, outils):
                return self._decision_securisee(
                    demande,
                    "Incohérence détectée entre l'agent choisi et les outils."
                )

            return {
                "agent": agent,
                "complexite": complexite,
                "analyse": {
                    "difficulte": data.get(
                        "difficulte",
                        "moyenne"
                    ),
                    "risques": data.get(
                        "risques",
                        "faible"
                    ),
                    "validation_requise": data.get(
                        "validation_requise",
                        False
                    ),
                    "resume": data.get(
                        "resume",
                        demande
                    )
                },
                "outils_suggeres": outils
            }

        except Exception as erreur:
            print(
                "[DecisionEngine] Erreur de décision : "
                f"{type(erreur).__name__}: {erreur}"
            )

            return defaut

