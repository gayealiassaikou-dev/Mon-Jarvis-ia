# Etat de Jarvis - 15 novembre 2026

## Note globale : 92%

## Architecture

### Modules core/ (54 fichiers)

**Streaming LLM** : `ai_providers._demander_gemini(on_chunk)` -> `ai_router.demander(on_chunk)` -> `ai_engine.demander(on_chunk)` -> `jarvis.traiter_commande(on_chunk)` -> `/chat/stream` SSE chunks

### Autres modules
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

input -> jarvis.traiter_commande(on_chunk=...)
  -> DecisionEngine (choix agent, tri dynamique providers)
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
- **Streaming LLM natif Gemini** (chunks phrase par phrase)
- Notifications Android
- Sync auto FTS5
- Retry + conseils apprentissage actif
- Kill switch session (100 appels/process)
- Kill switch mission (15 appels/mission)

### Performance
- Tri providers dynamique
- Circuit breaker 3 echecs
- Descriptions agents raccourcies (-300 tokens)

### Structure
- Split tools.py : 1273 -> 46 lignes + 6 modules
- Split jarvis.py : 723 -> 432 lignes (startup.py, voice_loop.py)
- Split decision_engine.py : 710 -> 215 lignes (decision_config, decision_local, decision_core)
- Archivage orchestrator.py (267L code mort)

## Tests

- **188 tests** (dont 26 offline sans LLM)
- test_deterministic_offline.py - 5 tests
- test_faux_succes.py - 5 tests
- test_quota_guard.py - 2 tests
- test_espace_travail_double.py - 3 tests
- test_e2e_pipeline.py - 5 tests (mockes)
- test_e2e_reel.py - 1 test (@pytest.mark.llm, protege par marker)
- conftest.py - patch budget sauf pour @llm
- pytest.ini - marker `llm` exclu par defaut

## Budget

- Journalier : 500 appels max
- Session : 100 appels max
- Tokens : 500k/jour

## Latences

| Scenario | Avant | Apres |
|---|---|---|
| Choix agent | 12s | 4.4s |
| Moteur simple (Gemini 1er) | 15-20s | **1.9s** |
| Pipeline complet 3 sous-taches | 30-44s | **12-13s** |
| Deterministe | 20-40s | 0-0.8s |
| Streaming premiere phrase | N/A | ~1s (au lieu de 3s+) |

## Limites connues

1. **Streaming Gemini uniquement** (Groq/Mistral/OpenRouter pas encore streames)
2. Velixir prod : P50 1.2s (free tier lent, pas le code)
3. Groq lent (~15-20s) - retrogade apres Gemini
4. verifiers.py 775L - dernier gros module
5. Supabase dependance critique (fallback local si down)
6. Test E2E reel manuel (`pytest -m llm` a lancer explicitement)

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

1. Streaming OpenAI-compatibles (Groq/Mistral) - 1h
2. Split verifiers.py (775L) - 2h
3. Test charge prod Velixir (script `scripts/test_charge_velixir.py`) - 30 min
4. Fix residus E2E (`.github/workflows` genere par LLM pendant tests)
5. Migrer Velixir vers Render/Fly.io si prod reelle (latence free tier)

## Historique

- 15/11/2026 : ~44 commits, 92% (vs 72% matin). Streaming LLM natif, split tools/jarvis/decision_engine, SSE, notifications, kill switches, apprentissage actif, 26 tests offline, 10 bugs fixes
