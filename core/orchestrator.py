"""Orchestration sequentielle et validee des agents specialises."""

import json

from .agent_permissions import obtenir_outils_autorises


class Orchestrator:
    AGENTS_INTERDITS = {"00_directeur_ia", "11_gestionnaire_outils_ia"}
    MAX_SOUS_TACHES = 8
    MAX_OBJECTIF = 1000

    def __init__(
        self, mission_manager, agent_manager, ai_engine,
        validation_manager, decision_engine, logger=None
    ):
        self.mission_manager = mission_manager
        self.agent_manager = agent_manager
        self.ai_engine = ai_engine
        self.validation_manager = validation_manager
        self.decision_engine = decision_engine
        self.logger = logger

    def _extraire_json(self, reponse):
        texte = str(reponse or "").strip()
        if texte.startswith("```"):
            lignes = texte.splitlines()
            lignes = lignes[1:]
            if lignes and lignes[-1].strip() == "```":
                lignes = lignes[:-1]
            texte = "\n".join(lignes).strip()

        debut = texte.find("{")
        fin = texte.rfind("}")
        if debut < 0 or fin < debut:
            raise ValueError("Le plan ne contient pas de JSON valide.")
        return json.loads(texte[debut:fin + 1])

    def valider_plan(self, plan):
        if not isinstance(plan, dict):
            raise ValueError("Le plan doit etre un objet JSON.")

        taches = plan.get("sous_taches")
        if not isinstance(taches, list) or not taches:
            raise ValueError("Le plan doit contenir au moins une sous-tache.")
        if len(taches) > self.MAX_SOUS_TACHES:
            raise ValueError("Le plan depasse 8 sous-taches.")

        agents_disponibles = getattr(self.agent_manager, "agents", {})
        resultat = []

        for index, tache in enumerate(taches):
            if not isinstance(tache, dict):
                raise ValueError(f"Sous-tache {index} invalide.")

            agent = tache.get("agent")
            objectif = tache.get("objectif")
            dependances = tache.get("dependances", [])
            action_requise = tache.get("action_requise", False)

            if not isinstance(agent, str) or agent not in agents_disponibles:
                raise ValueError(f"Agent inconnu pour la sous-tache {index}.")
            if agent in self.AGENTS_INTERDITS:
                raise ValueError(f"Agent interdit : {agent}.")
            if not obtenir_outils_autorises(agent):
                raise ValueError(f"Aucun outil autorise pour {agent}.")
            if not isinstance(objectif, str) or not objectif.strip():
                raise ValueError(f"Objectif vide pour la sous-tache {index}.")
            if len(objectif.strip()) > self.MAX_OBJECTIF:
                raise ValueError(f"Objectif trop long pour la sous-tache {index}.")
            if not isinstance(dependances, list):
                raise ValueError(f"Dependances invalides pour la sous-tache {index}.")
            if any(
                not isinstance(dep, int) or isinstance(dep, bool)
                or dep < 0 or dep >= index
                for dep in dependances
            ):
                raise ValueError(
                    "Chaque dependance doit designer une sous-tache precedente."
                )
            if len(dependances) != len(set(dependances)):
                raise ValueError(f"Dependance repetee pour la sous-tache {index}.")
            if not isinstance(action_requise, bool):
                raise ValueError("action_requise doit etre booleen.")

            resultat.append({
                "agent": agent,
                "objectif": objectif.strip(),
                "dependances": list(dependances),
                "action_requise": action_requise,
            })

        return {
            "nom": str(plan.get("nom") or "Mission multi-agents")[:120],
            "sous_taches": resultat,
        }

    def planifier(self, demande):
        agents = sorted(getattr(self.agent_manager, "agents", {}).keys())

        prompt = (
            "Tu es le planificateur de Sam Sarr. Decompose la demande en "
            "sous-taches distinctes executables par des agents specialises. "
            "Reponds uniquement en JSON sous cette forme : "
            '{"nom":"...","sous_taches":[{"agent":"nom_exact",'
            '"objectif":"...","dependances":[],"action_requise":false}]}. '
            "Utilise uniquement les agents disponibles. N'utilise jamais "
            "00_directeur_ia ni 11_gestionnaire_outils_ia. Les dependances "
            "sont des indices de sous-taches precedentes, a partir de zero. "
            "action_requise vaut true si une modification ou action est "
            "necessaire, sinon false. Maximum 8 sous-taches.\n\n"
            f"Agents disponibles : {agents}\n"
            f"Demande : {demande}"
        )

        reponse = self.ai_engine.demander(
            prompt, outils_autorises=[], mode_action=False
        )
        return self.valider_plan(self._extraire_json(reponse))

    def executer(self, demande, plan=None):
        mission = None

        try:
            plan_valide = (
                self.valider_plan(plan)
                if plan is not None
                else self.planifier(demande)
            )

            agents = list(dict.fromkeys(
                t["agent"] for t in plan_valide["sous_taches"]
            ))

            mission = self.mission_manager.creer_mission(
                plan_valide["nom"],
                objectif=demande,
                agents=agents,
                priorite="haute",
            )
            mission_id = mission["id"]

            # Enregistrer toutes les sous-taches avant leur execution.
            ids = []
            for tache in plan_valide["sous_taches"]:
                dependances = [ids[i] for i in tache["dependances"]]
                sous_tache = self.mission_manager.ajouter_sous_tache(
                    mission_id,
                    tache["agent"],
                    tache["objectif"],
                    dependances=dependances,
                )
                ids.append(sous_tache["id"])

            self.mission_manager.mettre_a_jour_statut(
                mission_id, "en_cours"
            )

            resultats = []

            # Execution strictement sequentielle.
            for tache, sous_tache_id in zip(
                plan_valide["sous_taches"], ids
            ):
                self.mission_manager.mettre_a_jour_sous_tache(
                    mission_id, sous_tache_id, "en_cours"
                )

                agent = tache["agent"]
                outils = (
                    list(obtenir_outils_autorises(agent))
                    if tache["action_requise"]
                    else []
                )
                contexte_agent = self.decision_engine.obtenir_contexte_agent(
                    agent
                )

                contexte = (
                    f"Mission globale : {demande}\n"
                    f"Agent specialise : {agent}\n"
                    f"Instructions de l'agent :\n{contexte_agent}"
                )

                reponse = self.ai_engine.demander(
                    tache["objectif"],
                    contexte=contexte,
                    outils_autorises=outils,
                    mode_action=bool(tache["action_requise"] and outils),
                    message_utilisateur_origine=demande,
                )

                # Copier les resultats avant le prochain appel AIEngine.
                resultats_outils = [
                    dict(r) if isinstance(r, dict) else r
                    for r in (
                        getattr(
                            self.ai_engine,
                            "derniers_resultats_outils",
                            []
                        ) or []
                    )
                ]

                validation = self.validation_manager.valider(
                    reponse,
                    mission_id=mission_id,
                    resultats_outils=resultats_outils,
                    outils_attendus=tache["action_requise"],
                )

                resultat_tache = {
                    "reponse": reponse,
                    "resultats_outils": resultats_outils,
                    "validation": validation,
                }

                if not validation.get("valide"):
                    self.mission_manager.mettre_a_jour_sous_tache(
                        mission_id,
                        sous_tache_id,
                        "bloquee",
                        resultat=resultat_tache,
                    )
                    self.mission_manager.mettre_a_jour_statut(
                        mission_id, "bloquee"
                    )
                    return {
                        "succes": False,
                        "mission_id": mission_id,
                        "sous_tache_bloquee": sous_tache_id,
                        "resultats": resultats + [resultat_tache],
                        "erreur": validation,
                    }

                self.mission_manager.mettre_a_jour_sous_tache(
                    mission_id,
                    sous_tache_id,
                    "terminee",
                    resultat=resultat_tache,
                )
                resultats.append(resultat_tache)

            self.mission_manager.mettre_a_jour_statut(
                mission_id, "terminee"
            )
            return {
                "succes": True,
                "mission_id": mission_id,
                "resultats": resultats,
            }

        except Exception as erreur:
            if mission and mission.get("id"):
                actuelle = self.mission_manager.obtenir_mission(
                    mission["id"]
                )
                if actuelle and actuelle.get("statut") == "en_cours":
                    self.mission_manager.mettre_a_jour_statut(
                        mission["id"], "bloquee"
                    )

            return {
                "succes": False,
                "mission_id": mission.get("id") if mission else None,
                "erreur": f"{type(erreur).__name__}: {erreur}",
            }
