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
from core.agent_permissions import obtenir_outils_autorises
from core.contexte_ia import charger_contexte
from core.paths import PROJECT_ROOT
from core.reprise import sauvegarder_point
from core.tools import _obtenir_nom_projet_actif


class Jarvis:
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
        self.contexte = charger_contexte()
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

    def start(self):
        if not self.system_checker.verifier():
            print("Erreur : système incomplet.")
            return

        self.logger.enregistrer("Démarrage de Jarvis")

        print(f"{self.nom} version {self.version} démarré.")
        print("Mémoire chargée.")
        self.agent_manager.afficher_agents()
        self.skill_manager.afficher_skills()
        self.brain_manager.afficher_brain()
        self.task_manager.afficher_taches()
        self.project_manager.afficher_projets()
        self.knowledge_manager.afficher_connaissances()
        self.mission_manager.afficher_missions()
        print("Système prêt.")

        mots_declencheurs_vocal = [
            "parle moi",
            "parle-moi",
            "je veux parler",
            "vocal",
            "voix",
            "parler"
        ]

        mots_retour_texte = [
            "reviens en texte",
            "stop vocal",
            "mode texte",
            "retour texte",
            "retourne en texte",
            "mode écriture",
            "mode ecriture",
            "passe en texte",
            "repasse en texte"
        ]

        derniere_reponse_texte = None

        while True:
            try:
                commande = input("Vous : ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                self.logger.enregistrer("Arrêt de Jarvis")
                print("Sam Sarr arrêté.")
                break

            if not commande:
                continue

            commande_lower = commande.lower()

            if commande_lower in ["quitter", "exit", "stop"]:
                self.logger.enregistrer("Arrêt de Jarvis")
                print("Sam Sarr arrêté.")
                break

            commandes_lecture = (
                "lis tout le résultat à haute voix",
                "lis tout le resultat a haute voix",
                "lis la dernière réponse",
                "lis la derniere reponse",
                "lis ta réponse à haute voix",
                "lis ta reponse a haute voix",
                "lis le résultat à haute voix",
                "lis le resultat a haute voix",
                "lis à haute voix",
                "lis a haute voix",
                "réponds-moi à haute voix",
                "reponds-moi a haute voix",
                "réponds moi à haute voix",
                "reponds moi a haute voix",
                "répond moi à haute voix",
                "repond moi a haute voix",
                "réponds à haute voix",
                "reponds a haute voix",
            )

            phrase_lecture = next(
                (p for p in commandes_lecture if p in commande_lower),
                None
            )

            import re as _re
            motif_lecture = None
            if not phrase_lecture:
                motif_lecture = _re.search(
                    r"\b(?:(?:lis|lire|lit|réponds|reponds|répond|repond|dis)(?:[- ]moi)?(?:[- ](?:le|la))?\s*(?:le\s+r[ée]sultat|la\s+r[ée]ponse|ta\s+r[ée]ponse|tout)?\s*)?(?:[àa]\s+)?(?:haute voix|voix haute)\b",
                    commande_lower
                )

            if phrase_lecture or motif_lecture:
                if phrase_lecture:
                    debut_phrase = commande_lower.index(phrase_lecture)
                    fin_phrase = debut_phrase + len(phrase_lecture)
                else:
                    debut_phrase = motif_lecture.start()
                    fin_phrase = motif_lecture.end()
                question = (
                    commande[:debut_phrase] + commande[fin_phrase:]
                ).strip(" ,.!?;:-")
                question = _re.sub(r"\s+et$", "", question, flags=_re.IGNORECASE).strip(" ,.!?;:-")

                if question:
                    reponse = self.traiter_commande(
                        question,
                        retourner_reponse=True
                    )
                    if isinstance(reponse, str) and reponse.strip():
                        derniere_reponse_texte = reponse
                        print("[Lecture de la réponse à haute voix...]")
                        self.voice_manager.parler(reponse)
                elif derniere_reponse_texte:
                    print("[Lecture de la dernière réponse...]")
                    self.voice_manager.parler(derniere_reponse_texte)
                else:
                    print("Aucune réponse précédente à lire.")
                continue

            if any(mot in commande_lower for mot in mots_declencheurs_vocal):
                self.mode_vocal(mots_retour_texte)
                continue

            reponse_texte = self.traiter_commande(
                commande,
                retourner_reponse=True
            )
            if isinstance(reponse_texte, str) and reponse_texte.strip():
                derniere_reponse_texte = reponse_texte

    def mode_vocal(self, mots_retour_texte):
        print()
        print("=" * 50)
        print("🎙️ MODE VOCAL ACTIVÉ")
        print("Dites « reviens en texte » pour quitter.")
        print("=" * 50)

        derniere_reponse = None
        self._erreurs_vocales = 0

        self.voice_manager.parler(
            "Mode vocal activé. Parle après ce message, je t'écoute."
        )

        while True:
            try:
                print()
                print("[🎙️ Écoute directe — parlez...]" )

                commande_vocale = self.voice_manager.ecouter_et_transcrire(5)

                if not commande_vocale:
                    print("[Aucune parole détectée.]")
                    continue

                if commande_vocale.startswith("Erreur"):
                    if "aucune parole" in commande_vocale.lower():
                        print("[Silence, je continue d'écouter.]")
                        continue
                    print(f"[Erreur vocale] {commande_vocale}")
                    self._erreurs_vocales += 1
                    if self._erreurs_vocales >= 3:
                        print("[Trop d'erreurs, retour au mode texte.]")
                        self.voice_manager.parler("Trop d'erreurs. Je repasse en mode texte.")
                        break
                    continue

                print(f"👤 Vous : {commande_vocale}")
                self._erreurs_vocales = 0

                commande_lower = commande_vocale.lower().strip()

                # ---------------------------------------------------------
                # MODE ÉCOUTE DIRECTE
                # Le mot d'activation "Jarvis" est désactivé.
                # Toute phrase transcrite est traitée directement.
                # ---------------------------------------------------------
                print(f"[🎤 Commande vocale directe : {commande_vocale}]")

                # ---------------------------------------------------------
                # COMMANDES LOCALES : DATE ET HEURE
                # Ces commandes ne doivent pas passer par l'IA.
                # Le command_manager possède déjà la logique locale.
                # ---------------------------------------------------------
                reponse_locale = self.command_manager.traiter(commande_vocale)

                if reponse_locale.startswith(("Il est ", "Nous sommes ")):
                    print("[⚡ Commande locale date/heure.]")
                    derniere_reponse = reponse_locale
                    print("[🔊 Sam Sarr parle...]")
                    self.voice_manager.parler(reponse_locale)
                    continue


                if any(mot in commande_lower for mot in mots_retour_texte):
                    print()
                    print("[📝 Retour au mode texte.]")
                    self.voice_manager.parler(
                        "D'accord. Je repasse en mode texte."
                    )
                    break

                if commande_lower in ["quitter", "exit", "arrête jarvis", "arrête toi"]:
                    self.voice_manager.parler("D'accord. J'arrête Sam Sarr.")
                    self.logger.enregistrer("Arrêt de Jarvis par commande vocale")
                    print("Sam Sarr arrêté.")
                    return

                if commande_lower in [
                    "plus lentement",
                    "parle plus lentement",
                    "ralentis",
                    "ralentis ta voix"
                ]:
                    self.voice_manager.definir_vitesse(0.8)
                    self.voice_manager.parler(
                        "D'accord, je parle plus lentement."
                    )
                    continue

                if commande_lower in [
                    "plus rapidement",
                    "parle plus rapidement",
                    "accélère",
                    "accelere",
                    "accélère ta voix",
                    "accelere ta voix"
                ]:
                    self.voice_manager.definir_vitesse(1.2)
                    self.voice_manager.parler(
                        "D'accord, je parle plus rapidement."
                    )
                    continue

                if commande_lower in [
                    "vitesse normale",
                    "reviens à la vitesse normale",
                    "reviens a la vitesse normale",
                    "revient à la vitesse normale",
                    "revient a la vitesse normale"
                ]:
                    self.voice_manager.definir_vitesse(1.0)
                    self.voice_manager.parler(
                        "D'accord, je reviens à une vitesse normale."
                    )
                    continue

                if commande_lower in ["répète", "repete", "répète ça", "repete ça"]:
                    if derniere_reponse:
                        print("[🔁 Répétition de la dernière réponse.]")
                        self.voice_manager.parler(derniere_reponse)
                    else:
                        self.voice_manager.parler(
                            "Je n'ai pas encore de réponse à répéter."
                        )
                    continue

                print("[🧠 Sam Sarr réfléchit...]")

                reponse = self.traiter_commande(
                    commande_vocale,
                    retourner_reponse=True
                )

                if reponse:
                    derniere_reponse = reponse
                    print("[🔊 Sam Sarr parle...]")
                    self.voice_manager.parler(reponse)

            except KeyboardInterrupt:
                print()
                print("[Retour au mode texte.]")
                break
            except Exception as e:
                print(f"[Erreur mode vocal] {e}")
                self.voice_manager.parler(
                    "Une erreur est survenue. Je continue à t'écouter."
                )

    def traiter_commande(self, commande, retourner_reponse=False,
                         activity_tracker=None, demande_id=None):
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
            suivre("Choix de l'agent", "en_cours")
            debut_mesure = time.perf_counter()
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
                self.contexte + "\n\n" + contexte_agent + "\n\n" + regle_securite
            )
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
            outils_autorises_agent = obtenir_outils_autorises(agent)
            outils_autorises = [
                outil for outil in outils_suggeres
                if outil in outils_autorises_agent
            ]

            suivre("Appel du moteur IA", "en_cours")
            debut_mesure = time.perf_counter()
            reponse = self.ai_engine.demander(
                commande,
                contexte=contexte_complet,
                historique=historique,
                outils_autorises=outils_autorises,
                mode_action=bool(outils_autorises),
            )
            self.logger.enregistrer(
                f"[PERFORMANCE] Appel principal du moteur IA : {time.perf_counter() - debut_mesure:.2f} s"
            )
            suivre("Validation de la réponse", "en_cours")
            validation = self.validation_manager.valider(
                reponse, mission_id, self.ai_engine.derniers_resultats_outils,
                outils_attendus=bool(outils_autorises),
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
            if isinstance(reponse, str) and not reponse.startswith("Erreur IA") and not reponse.startswith("Toutes les IA sont indisponibles"):
                reponse_a_memoriser = reponse.replace("[Secours Gemini] ", "").strip()
                self.memory_manager.ajouter_echange(commande, reponse_a_memoriser)

            if retourner_reponse:
                return reponse

        else:
            print(resultat)
            if retourner_reponse:
                return resultat
