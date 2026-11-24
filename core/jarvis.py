import json
import os
import time
from core.agent_manager import AgentManager
from core.command_manager import CommandManager
from core.local_brain import LocalBrain
from core.memory_manager import MemoryManager
from core.skill_manager import SkillManager
from core.brain_manager import BrainManager
from core.logger import Logger
from core.system_checker import SystemChecker
from core.task_manager import TaskManager
from core.project_manager import ProjectManager
from core.data_manager import DataManager
from core.event_manager import EventManager
from core.context_manager import ContextManager
from core.knowledge_manager import KnowledgeManager
from core.decision_engine import DecisionEngine
from core.mission_manager import MissionManager
from core.coordination_manager import CoordinationManager
from core.validation_manager import ValidationManager
from core.voice_manager import VoiceManager
from core.ai_engine import AIEngine
from core.voice_loop import VoiceLoopMixin
from core.startup import StartupMixin
from core.tool_guard import filtrer_outils_pour_agent
from core.contexte_ia import charger_contexte
from core.paths import PROJECT_ROOT
from core.reprise import sauvegarder_point
from core.tools import _obtenir_nom_projet_actif, lire_etat_projets_taches


class Jarvis(StartupMixin, VoiceLoopMixin):
    def __init__(self):
        self.config = self.charger_config()
        self.memory_manager = MemoryManager()
        self.agent_manager = AgentManager()
        self.command_manager = CommandManager()
        self.brain_manager = BrainManager()
        self.local_brain = LocalBrain(self.brain_manager)
        self.skill_manager = SkillManager()
        self.logger = Logger()
        self.system_checker = SystemChecker()
        self.task_manager = TaskManager()
        self.project_manager = ProjectManager()
        self.data_manager = DataManager()
        self.event_manager = EventManager()
        self.context_manager = ContextManager()
        self.knowledge_manager = KnowledgeManager()

        self.ai_engine = AIEngine(memory_manager=self.memory_manager, logger=self.logger)
        _ctx = charger_contexte()
        _i = _ctx.find("FAITS VERIFIES SUR SAM SARR")
        _j = _ctx.find("PROFIL_PROGRAMMATION_SAMBA_SARR")
        if 0 <= _i < _j:
            self.contexte = _ctx[:_i] + _ctx[_j:]
            self.contexte_faits = _ctx[_i:_j].strip()
        else:
            self.contexte = _ctx
            self.contexte_faits = ""
        self.decision_engine = DecisionEngine(
            self.brain_manager,
            self.agent_manager,
            self.ai_engine
        )
        self.mission_manager = MissionManager()
        self.coordination_manager = CoordinationManager(self.mission_manager, self.logger)
        self.validation_manager = ValidationManager(self.logger)
        self.ai_engine.validation_manager = self.validation_manager
        self.voice_manager = VoiceManager()

        self.nom = self.config["nom"]
        self.version = self.config["version"]

    def charger_config(self):
        chemin = PROJECT_ROOT / "config" / "settings.json"

        with open(chemin, "r", encoding="utf-8") as fichier:
            return json.load(fichier)

    def traiter_commande(self, commande, retourner_reponse=False,
                         activity_tracker=None, demande_id=None,
                         agent_force=None, on_chunk=None):
        def suivre(message, statut="information"):
            if activity_tracker is not None and demande_id is not None:
                try:
                    activity_tracker.ajouter_etape(demande_id, message, statut)
                except Exception:
                    pass  # Le suivi ne doit jamais bloquer le traitement.

        # Nouvelle commande utilisateur = nouvelle fenêtre de correction automatique.
        self.validation_manager.corrections_utilisees = 0
        self.logger.enregistrer(f"Commande reçue : {commande}")
        suivre("Analyse de la demande", "en_cours")

        resultat = self.command_manager.traiter(commande)

        # Deterministe (0 LLM) : actions Android simples (torche, batterie, volume, wifi)
        if "Commande inconnue" in resultat:
            try:
                from core import deterministic_actions
                _outils_deterministes = deterministic_actions.OUTILS_DETERMINISTES
                if agent_force:
                    _outils_deterministes = filtrer_outils_pour_agent(
                        agent_force, _outils_deterministes
                    )
                _det = deterministic_actions.tenter(
                    commande,
                    agent=agent_force,
                    outils_autorises=_outils_deterministes,
                )
                if _det and _det.get("ok"):
                    _msg = _det.get("message", "OK")
                    self.logger.enregistrer(f"[DETERMINISTE] {_det.get('outil')}")
                    self.memory_manager.ajouter_echange(commande, _msg)
                    if retourner_reponse:
                        return _msg
                    print(_msg)
                    return
            except Exception:
                pass

        if "Commande inconnue" in resultat:
            # Les recherches GitHub doivent passer par le moteur de décision,
            # jamais être interceptées par les fiches de connaissances locales.
            demande_normalisee = str(commande).casefold()
            recherche_github = any(mot in demande_normalisee for mot in (
                "github", "git hub", "repository"
            ))
            reponse_locale = (
                None if recherche_github
                else self.local_brain.repondre(commande)
            )
            if reponse_locale is not None:
                print(reponse_locale)
                self.logger.enregistrer(
                    "[LOCAL] Réponse fournie sans fournisseur IA."
                )
                self.memory_manager.ajouter_echange(
                    commande, reponse_locale
                )
                if retourner_reponse:
                    return reponse_locale
                return
            # Interception planification : "planifie X en N etapes"
            import re as _re_plan
            m_plan = _re_plan.match(r"^\s*(?:planifie|planifier|organise|decompose)(?:\s+et\s+(?:execute|executer|lance|lance))?\s+(.+?)(?:\s+en\s+(\d+)\s+(?:etapes?|taches?|sous-taches?))?\s*$", commande, _re_plan.IGNORECASE)
            _do_execute = bool(_re_plan.search(r"\bet\s+(?:execute|executer|lance|lance)\b", commande, _re_plan.IGNORECASE))
            if m_plan and not agent_force:
                objectif = m_plan.group(1).strip()
                try:
                    from core.mission_manager import MissionManager as _MM
                    _mm = _MM()
                    _mission = _mm.creer_mission(nom=objectif, objectif="Cree par Jarvis via commande planifie", priorite="normale")
                    _mm.mettre_a_jour_statut(_mission["id"], "en_cours")
                    from core.mission_planner import planifier as _planifier
                    _plan = _planifier(_mission["id"])
                    if _plan.get("ok"):
                        msg = f"Mission {_mission['id']} planifiee en {_plan['nb']} sous-taches."
                        if _do_execute:
                            from core.subtask_executor import executer_mission as _exec
                            _res = _exec(_mission["id"])
                            if _res.get("ok"):
                                msg += f" Execution OK ({_res.get('etapes')} etapes, statut {_res.get('statut')})."
                            else:
                                msg += f" Execution echouee : {_res.get('statut')}."
                        else:
                            msg += " Lance `python -m core.mission_runner --max 1` pour executer."
                    else:
                        _mm.mettre_a_jour_statut(_mission["id"], "bloquee")
                        msg = f"Mission {_mission['id']} creee mais planification echouee : {_plan.get('erreur')}"
                except Exception as _e:
                    msg = f"Erreur planification : {type(_e).__name__}: {_e}"
                print(msg)
                self.logger.enregistrer(f"[PLANIFIER] {msg}")
                self.memory_manager.ajouter_echange(commande, msg)
                if retourner_reponse:
                    return msg
                return

            suivre("Choix de l'agent", "en_cours")
            debut_mesure = time.perf_counter()
            if agent_force:
                decision = {"agent": agent_force, "analyse": {"risques": "aucun"}, "outils_suggeres": []}
                self.logger.enregistrer(f"[PERFORMANCE] Agent force : {agent_force}")
            else:
                decision = self.decision_engine.decider(commande)
                self.logger.enregistrer(
                    f"[PERFORMANCE] Choix de l'agent : {time.perf_counter() - debut_mesure:.2f} s"
                )
            agent = decision["agent"]
            analyse = decision["analyse"]

            self.coordination_manager.preparer(decision, commande)

            mission_id = None
            print(f"[Agent : {agent}]")
            if analyse.get("validation_requise"):
                print(f"[Attention : cette action peut avoir un impact important - risques : {analyse.get('risques')}]")
                mission = self.mission_manager.creer_mission(
                    nom=analyse.get("resume", commande),
                    objectif=commande,
                    agents=[agent],
                    priorite="haute" if analyse.get("risques") in ["moyen", "eleve"] else "normale"
                )
                mission_id = mission["id"]
                print(f"[Mission creee : {mission_id}]")
                self.coordination_manager.demarrer_mission(mission_id)

            suivre("Préparation du contexte", "en_cours")
            contexte_agent = self.decision_engine.obtenir_contexte_agent(agent)
            regle_securite = (
                "REGLES DE SECURITE (tous les agents) : ne demande jamais a "
                "l'utilisateur de fournir, coller ou envoyer un jeton (PAT), "
                "une cle API, un mot de passe ou tout autre secret dans la "
                "conversation. Si une action GitHub est impossible, explique "
                "simplement que les outils GitHub fonctionnent depuis la "
                "version Termux (telephone) et pas depuis la version en ligne, "
                "et propose de la faire depuis Termux. Quand on te demande "
                "si tu peux faire quelque chose, reponds par oui ou non et "
                "explique ce qui est possible, sans lancer d'action tant que "
                "la demande n'est pas explicite."
            )
            contexte_complet = (
                self.contexte + (("\n\n" + self.contexte_faits) if self.contexte_faits and any(m in str(commande).casefold() for m in ("sam", "sarr", "outils", "agent", "internet", "web", "modele", "modèle", "memoire", "mémoire", "historique", "capacite", "capacité", "acces", "accès", "connaissance", "peux-tu", "peux tu", "que sais")) else "") + "\n\n" + contexte_agent + "\n\n" + regle_securite
            )
            # Projets et tâches : transmettre l'état actuel au moteur IA.
            try:
                etat_projets = lire_etat_projets_taches()
                projets = etat_projets.get("projets", [])
                if isinstance(projets, list) and projets:
                    lignes_projets = [
                        f"- {p.get('nom', '').strip()} (statut : {p.get('statut', 'non précisé')})"
                        for p in projets
                        if isinstance(p, dict) and isinstance(p.get("nom"), str) and p["nom"].strip()
                    ]
                    if lignes_projets:
                        contexte_complet += (
                            "\n\nProjets enregistrés :\n" + "\n".join(lignes_projets)
                        )
            except Exception as e:
                self.logger.warning(f"Impossible de charger les projets dans le contexte : {e}")
            # Mémoire à long terme : souvenirs pertinents pour cette demande.
            try:
                souvenirs = self.memory_manager.rechercher_souvenirs_pertinents(commande, limite=5)
                if souvenirs:
                    contexte_complet += (
                        "\n\nSouvenirs pertinents (mémoire à long terme) :\n"
                        + "\n".join(s[:300] for s in souvenirs)
                    )
            except Exception:
                pass

            historique = self.memory_manager.obtenir_historique_recent()

            # Le DecisionEngine choisit les outils nécessaires à cette demande.
            # On applique une seconde fois les permissions de l'agent
            # avant de transmettre les outils à l'AIEngine.
            outils_suggeres = decision.get("outils_suggeres", [])
            outils_autorises = filtrer_outils_pour_agent(
                agent, outils_suggeres
            )

            suivre("Appel du moteur IA", "en_cours")
            debut_mesure = time.perf_counter()
            reponse = self.ai_engine.demander(
                commande,
                contexte=contexte_complet,
                historique=historique,
                outils_autorises=outils_autorises,
                mode_action=bool(outils_autorises),
                on_chunk=on_chunk,
                agent=agent,
            )
            self.logger.enregistrer(
                f"[PERFORMANCE] Appel principal du moteur IA : {time.perf_counter() - debut_mesure:.2f} s"
            )
            suivre("Validation de la réponse", "en_cours")
            validation = self.validation_manager.valider(
                reponse, mission_id, self.ai_engine.derniers_resultats_outils,
                outils_attendus=bool(outils_autorises) or any(
                    isinstance(o, str) and o in str(commande)
                    for o in self.decision_engine.outils_disponibles
                ),
            )

            # Le CoordinationManager décide de la suite à donner.
            if not validation["valide"]:
                suite_action = self.coordination_manager.decider_suite_action(
                    self.ai_engine.derniers_resultats_outils,
                    validation,
                    self.validation_manager
                )

                if suite_action["decision"] == "corriger":
                    diagnostic = suite_action.get("diagnostic", {})
                    outil = diagnostic.get("outil")

                    print(
                        f"[Correction automatique : nouvelle tentative unique pour "
                        f"{outil}]"
                    )

                    if outil and self.ai_engine.rejouer_outil_echoue(
                        outil, outils_autorises
                    ):
                        # Le rejeu a réussi : on récupère son résultat vérifié.
                        resultat_correction = None
                        for resultat in reversed(self.ai_engine.derniers_resultats_outils):
                            if resultat.get("outil") == outil:
                                resultat_correction = resultat
                                break

                        verification_correction = (
                            resultat_correction.get("verification", {})
                            if resultat_correction
                            else {}
                        )

                        if verification_correction.get("verifie") is True:
                            print("[Correction automatique reussie]")

                            # Nouvelle réponse du modèle basée sur le résultat corrigé.
                            # Aucun outil n'est transmis ici afin d'éviter une nouvelle
                            # exécution du même outil.
                            contexte_correction = (
                                contexte_complet
                                + "\n\nRésultat de la correction automatique :\n"
                                + str(resultat_correction.get("resultat", ""))
                                + "\nLa vérification de l'action est réussie. "
                                "Réponds maintenant à la demande de l'utilisateur "
                                "en tenant compte de ce résultat, sans exécuter "
                                "d'autre outil."
                            )

                            debut_mesure = time.perf_counter()
                            reponse = self.ai_engine.demander(
                                commande,
                                contexte=contexte_correction,
                                historique=historique,
                                outils_autorises=[]
                            )
                            self.logger.enregistrer(
                                f"[PERFORMANCE] Appel de correction : {time.perf_counter() - debut_mesure:.2f} s"
                            )

                            # Si le modele ne fournit aucune reponse apres
                            # une correction pourtant verifiee, utiliser le
                            # resultat verifie de l'outil comme secours local.
                            if not reponse or not reponse.strip():
                                reponse = (
                                    "Correction automatique réussie et vérifiée. "
                                    + str(resultat_correction.get("resultat", ""))
                                )

                            validation = self.validation_manager.valider(
                                reponse,
                                mission_id,
                                self.ai_engine.derniers_resultats_outils
                            )
                        else:
                            self.logger.enregistrer(
                                "[Correction] Rejeu effectué mais vérification toujours échouée."
                            )
                    else:
                        self.logger.enregistrer(
                            "[Correction] Rejeu impossible."
                        )

                elif suite_action["decision"] == "bloquer":
                    correction = suite_action.get("correction", {})
                    self.logger.enregistrer(
                        f"[Correction] Refusee : "
                        f"{correction.get('raison', 'Correction non autorisee.')}"
                    )

            # VERROU : un échec réel ne doit jamais être présenté comme une réussite.
            if not validation["valide"]:
                avertissement = validation.get(
                    "avertissement",
                    "L'action n'a pas pu être validée."
                )

                print(f"[Validation echouee : {avertissement}]")

                if mission_id:
                    self.mission_manager.mettre_a_jour_statut(
                        mission_id, "bloquee"
                    )

                reponse = (
                    "Je n'ai pas pu confirmer la réussite de cette action. "
                    f"Raison : {avertissement}"
                )

            elif validation.get("avertissement"):
                print(
                    f"[Avertissement : {validation['avertissement']}]"
                )

            # Reprise : uniquement apres validation d'une action reelle.
            if validation.get("valide") is True:
                resultats = getattr(self.ai_engine, "derniers_resultats_outils", []) or []
                resultat = next(
                    (r for r in reversed(resultats)
                     if isinstance(r, dict)
                     and r.get("execute") is True
                     and r.get("statut") == "succes"
                     and isinstance(r.get("verification"), dict)
                     and r["verification"].get("verifie") is True
                     and r.get("outil") not in {
                         "definir_projet_actif", "obtenir_projet_actif"
                     }),
                    None,
                )
                if resultat is not None:
                    try:
                        projet = _obtenir_nom_projet_actif()
                        if projet:
                            source = sauvegarder_point(
                                projet,
                                derniere_action="Action verifiee : " + str(resultat.get("outil", "outil")),
                                derniere_etape="Execution et verification reussies",
                                prochaine_action="A determiner a la prochaine reprise",
                                fichiers=[],
                                contexte="Action confirmee par le moteur d'execution de Sam Sarr.",
                            )
                            self.logger.enregistrer(
                                f"[Reprise] Point sauvegarde ({source})."
                            )
                    except Exception as erreur:
                        try:
                            self.logger.enregistrer(
                                "[Reprise] Sauvegarde ignoree : " + type(erreur).__name__
                            )
                        except Exception:
                            pass

            self.coordination_manager.superviser_resultat(
                reponse,
                mission_id,
                validation=validation
            )
            reponse = self.coordination_manager.livrer(reponse, mission_id)

            print(reponse)
            if isinstance(reponse, str) and not reponse.startswith("Erreur IA") and not reponse.startswith("Toutes les IA sont indisponibles") and validation.get("valide") is True and not validation.get("avertissement"):
                reponse_a_memoriser = reponse.replace("[Secours Gemini] ", "").strip()
                self.memory_manager.ajouter_echange(commande, reponse_a_memoriser)

            if retourner_reponse:
                return reponse

        else:
            print(resultat)
            if retourner_reponse:
                return resultat
