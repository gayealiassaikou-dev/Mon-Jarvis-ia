# Etat de Jarvis - 15 novembre 2026

## Note globale : 84%

## Architecture

### Modules core/ (54 fichiers)
- **Orchestration** : jarvis.py (723L), mission_manager.py (301L), mission_runner.py, subtask_executor.py (217L), mission_planner.py
- **IA** : ai_engine.py (679L), ai_router.py (200L), ai_providers.py (311L), decision_engine.py (710L), tools_schema.py (498L), verifiers.py (775L)
- **Outils** : tools.py (46L reexports), tools_fichiers.py (354L), tools_python.py (318L), tools_github.py (406L), tools_projets.py (225L), tools_web.py (40L)
- **Memoire** : memory_manager.py (237L), memory_index.py (126L FTS5), learning.py (104L), supabase_*.py
- **Systeme** : budget_guard.py, notifications.py, triggers.py, trigger_engine.py
- **Interface** : dashboard.py, interface/app.py (275L SSE), voice_manager.py (656L)
- **Agents** : agent_permissions.py (76L), local_brain.py (802L, fallback 0-LLM)

### Agents (12)
00_directeur_ia, 01_developpeur, 02_designer, 03_recherche, 04_business, 05_architecte_ia, 06_memoire_ia, 07_automatisation_ia, 08_testeur_ia, 09_securite_ia, 10_assistant_vocal_ia, 11_gestionnaire_outils_ia

Utilises : 01_dev (43%), 08_testeur (38%), 00_directeur (8%), autres rares

## Providers IA

| Provider | Priorite | Statut | Latence |
|---|---|---|---|
| groq | 1 | actif | ~15-20s |
| mistral | 2 | pret | jamais appele |
| openrouter | 3 | pret | jamais appele |
| gemini | 5 | actif | ~2-5s |
| nvidia | 6 | actif | lent |

Tri dynamique : skipe apres 3 echecs, trie par latence.

## Pipeline mission

input -> jarvis.traiter_commande()
  -> DecisionEngine (choix agent)
  -> mission_planner (decomposition LLM)
  -> subtask_executor :
    1. Deterministe (fichiers/dossiers/projets/taches) = 0 LLM
    2. LLM normal
    3. Retry force (si pas code/JSON)
    4. Fallback JSON {action, parameters}
    5. Fallback ```python
  -> validation_manager (preuve outil)
  -> learning (memoire echecs/solutions)
  -> notifications Android

## Acquis 15/11/2026

### Bugs fixes
- executer_mission auto-planifie
- Regex contenu coupe au " et s..."
- Fallback JSON (3 formats)
- Fallback executer_script (code inline)
- Fallback execute les .py crees
- Retry conditionne au contenu
- Detection faux succes elargie
- Deadlock infini -> abandon 3 tentatives
- Chemin espace_travail/espace_travail/ corrige
- Tests casses par budget -> conftest.py autouse

### Features
- SSE backend /chat/stream
- SSE frontend interface web
- Notifications Android
- Sync auto FTS5
- Retry + conseils apprentissage
- Kill switch session (100 appels/process)

### Performance
- Tri providers dynamique
- Circuit breaker 3 echecs
- Descriptions agents raccourcies (-300 tokens)

### Structure
- Split tools.py : 1273 -> 46 lignes + 6 modules
- Archivage orchestrator.py (267L code mort)

## Tests

- 180 tests (dont 13 offline sans LLM)
- test_deterministic_offline.py - 5 tests
- test_faux_succes.py - 5 tests
- test_quota_guard.py - 2 tests
- conftest.py - patch auto budget

## Budget

- Journalier : 500 appels max
- Session : 100 appels max
- Tokens : 500k/jour

## Latences

| Scenario | Avant | Apres |
|---|---|---|
| Choix agent | 12s | 4.4s |
| Moteur complexe | 44s | 9.3s |
| Deterministe | 20-40s | 0-0.8s |
| Pipeline 2 sous-taches | 30s+ | 13.7s |

## Limites connues

1. Streaming etapes, pas mot-par-mot
2. Apprentissage passif (conseils injectes, retry auto pas boucle)
3. Groq lent (~15-20s/appel)
4. jarvis.py 723L - dernier monolithe
5. Tests E2E non automatises
6. Supabase dependance critique

## Commandes utiles

# Tests
python -m pytest tests/ -q

# Tests offline (0 LLM)
python -m pytest tests/test_deterministic_offline.py -v

# Budget
python -c "from core import budget_guard; print(budget_guard.etat())"

# Reset budget
python -c "import json; json.dump({'date': '2026-11-15', 'appels': 0, 'tokens_estimes': 0}, open('data/budget_journalier.json', 'w'))"

# Boucle autonomie
python -m core.mission_runner --watch --intervalle 60

# Dashboard
python -m core.dashboard

# Interface web
python -c "from interface.app import app; app.run(host='127.0.0.1', port=5001)"

## Prochaines priorites

1. Split jarvis.py (723L) -> 4-5 modules
2. Streaming mot-par-mot
3. Boucle apprentissage active
4. Test E2E automatise (1 LLM controle)
5. Kill switch par mission

## Historique

- 15/11/2026 : 25 commits, 84% (vs 72% matin). Split tools, SSE, notifications, kill switch, 10 bugs fixes
