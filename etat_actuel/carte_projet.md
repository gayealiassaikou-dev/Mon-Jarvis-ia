# Carte du projet

Generee le 2026-10-12 22:48

## core/__init__.py (1 lignes)
- Classes : aucune
- Fonctions : aucune
- Tests : AUCUN

## core/agent_manager.py (24 lignes)
- Classes : AgentManager
- Fonctions : aucune
- Tests : AUCUN

## core/agent_permissions.py (71 lignes)
- Classes : aucune
- Fonctions : obtenir_outils_autorises, filtrer_outils
- Tests : test_routage_testeur.py

## core/ai_engine.py (1682 lignes)
- Classes : AIEngine
- Fonctions : _convertir_outils_gemini
- Tests : test_bout_en_bout_outils.py, test_routeur_double_execution.py, test_validation_contraintes.py, test_verification_resultats.py

## core/ai_router.py (120 lignes)
- Classes : AIRouter
- Fonctions : masquer_secrets
- Tests : AUCUN

## core/brain_loader.py (35 lignes)
- Classes : BrainLoader
- Fonctions : aucune
- Tests : AUCUN

## core/brain_manager.py (72 lignes)
- Classes : BrainManager
- Fonctions : aucune
- Tests : AUCUN

## core/command_manager.py (81 lignes)
- Classes : CommandManager
- Fonctions : aucune
- Tests : AUCUN

## core/context_manager.py (15 lignes)
- Classes : ContextManager
- Fonctions : aucune
- Tests : AUCUN

## core/contexte_ia.py (56 lignes)
- Classes : aucune
- Fonctions : charger_contexte
- Tests : AUCUN

## core/coordination_manager.py (123 lignes)
- Classes : CoordinationManager
- Fonctions : aucune
- Tests : test_superviser_resultat.py

## core/data_manager.py (25 lignes)
- Classes : DataManager
- Fonctions : aucune
- Tests : AUCUN

## core/decision_engine.py (515 lignes)
- Classes : DecisionEngine
- Fonctions : aucune
- Tests : test_routage_testeur.py

## core/event_manager.py (14 lignes)
- Classes : EventManager
- Fonctions : aucune
- Tests : AUCUN

## core/github_manager.py (26 lignes)
- Classes : aucune
- Fonctions : verifier_github
- Tests : AUCUN

## core/jarvis.py (518 lignes)
- Classes : Jarvis
- Fonctions : aucune
- Tests : AUCUN

## core/knowledge_manager.py (28 lignes)
- Classes : KnowledgeManager
- Fonctions : aucune
- Tests : AUCUN

## core/logger.py (12 lignes)
- Classes : Logger
- Fonctions : aucune
- Tests : AUCUN

## core/main.py (10 lignes)
- Classes : aucune
- Fonctions : main
- Tests : AUCUN

## core/memory_manager.py (68 lignes)
- Classes : MemoryManager
- Fonctions : aucune
- Tests : AUCUN

## core/mission_manager.py (107 lignes)
- Classes : MissionManager
- Fonctions : aucune
- Tests : test_mission_manager.py

## core/paths.py (9 lignes)
- Classes : aucune
- Fonctions : aucune
- Tests : AUCUN

## core/project_manager.py (17 lignes)
- Classes : ProjectManager
- Fonctions : aucune
- Tests : AUCUN

## core/skill_manager.py (24 lignes)
- Classes : SkillManager
- Fonctions : aucune
- Tests : AUCUN

## core/system_checker.py (28 lignes)
- Classes : SystemChecker
- Fonctions : aucune
- Tests : AUCUN

## core/task_manager.py (15 lignes)
- Classes : TaskManager
- Fonctions : aucune
- Tests : AUCUN

## core/test_router_local.py (7 lignes)
- Classes : aucune
- Fonctions : aucune
- Tests : AUCUN

## core/test_voice.py (9 lignes)
- Classes : aucune
- Fonctions : aucune
- Tests : AUCUN

## core/tools.py (821 lignes)
- Classes : aucune
- Fonctions : _chemin_autorise, _fichier_protege, lire_fichier, ecrire_fichier, supprimer_fichier, lister_fichiers, creer_dossier, rechercher_web, _charger_donnees, _sauvegarder_donnees, lire_etat_projets_taches, creer_projet, ajouter_tache, lister_projets, lister_taches, _headers_github, _interpreter_erreur_github, github_creer_repo, github_lister_repos, github_lire_fichier, github_ecrire_fichier, terminer_tache, supprimer_tache, supprimer_projet, modifier_statut_projet, executer_tests_python
- Tests : test_routage_testeur.py

## core/validation_manager.py (387 lignes)
- Classes : ValidationManager
- Fonctions : aucune
- Tests : test_bout_en_bout_outils.py, test_outils_attendus.py, test_politique_correction.py

## core/voice_manager.py (640 lignes)
- Classes : VoiceManager
- Fonctions : aucune
- Tests : test_normalisation_stt.py

## Modules sans test dans tests/
- __init__.py
- agent_manager.py
- ai_router.py
- brain_loader.py
- brain_manager.py
- command_manager.py
- context_manager.py
- contexte_ia.py
- data_manager.py
- event_manager.py
- github_manager.py
- jarvis.py
- knowledge_manager.py
- logger.py
- main.py
- memory_manager.py
- paths.py
- project_manager.py
- skill_manager.py
- system_checker.py
- task_manager.py
- test_router_local.py
- test_voice.py

## Fichiers test_*.py a la racine (hors tests/)
- test_ai_router.py
- test_ai_router_reel.py
- test_assemblyai.py
- test_creation.py
- test_openrouter.py
- test_rejouer_outil_echoue.py
- test_routeur.py
- test_routeur_double_erreur.py
- test_routeur_independant.py
