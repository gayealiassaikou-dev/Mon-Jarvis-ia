"""Decompose une mission en sous-taches via LLM."""
import json
import os
import requests
from dotenv import load_dotenv

from core.mission_manager import MissionManager
from core.agent_permissions import PERMISSIONS_AGENTS

load_dotenv()

PROMPT = """Tu es le planificateur de Jarvis. Decoupe la mission en 2 a 4 sous-taches.

Mission: {nom}
Objectif: {objectif}

Agents disponibles: {agents}

Reponds UNIQUEMENT en JSON valide, sans texte autour:
{{"sous_taches":[{{"agent":"01_developpeur","objectif":"...","dependances":[]}},{{"agent":"08_testeur_ia","objectif":"...","dependances":[0]}}]}}

dependances = liste d'index (0-based) des sous-taches precedentes dont celle-ci depend."""


def _appeler_llm(prompt):
    providers = [
        {"nom": "groq", "url": "https://api.groq.com/openai/v1/chat/completions", "model": "openai/gpt-oss-120b", "env": "GROQ_API_KEY", "type": "openai"},
        {"nom": "mistral", "url": "https://api.mistral.ai/v1/chat/completions", "model": "mistral-small-latest", "env": "MISTRAL_API_KEY", "type": "openai"},
        {"nom": "gemini", "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent", "model": "gemini-flash-lite-latest", "env": "GEMINI_API_KEY", "type": "gemini"},
    ]
    erreurs = []
    for p in providers:
        key = os.getenv(p["env"])
        if not key:
            continue
        try:
            if p["type"] == "gemini":
                r = requests.post(f"{p['url']}?key={key}",
                                  json={"contents": [{"parts": [{"text": prompt}]}]},
                                  timeout=(5, 30))
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                r = requests.post(p["url"],
                                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                  json={"model": p["model"], "messages": [{"role": "user", "content": prompt}]},
                                  timeout=(5, 30))
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            erreurs.append(f"{p['nom']}: {type(e).__name__}")
            continue
    raise RuntimeError("Planner: aucun provider. " + " | ".join(erreurs))


def _nettoyer_json(t):
    t = t.strip()
    if t.startswith("```"):
        t = t.strip("`").strip()
        if t.startswith("json"):
            t = t[4:].strip()
    return t


def planifier(mission_id):
    mm = MissionManager()
    mission = mm.obtenir_mission(mission_id)
    if not mission:
        return {"erreur": "mission introuvable"}
    if mission.get("sous_taches"):
        return {"erreur": "deja planifiee", "nb": len(mission["sous_taches"])}

    agents = list(PERMISSIONS_AGENTS.keys())
    prompt = PROMPT.format(
        nom=mission["nom"],
        objectif=mission.get("objectif", ""),
        agents=", ".join(agents)
    )
    try:
        raw = _appeler_llm(prompt)
    except Exception as e:
        return {"erreur": f"LLM: {type(e).__name__}: {str(e)[:150]}"}

    try:
        data = json.loads(_nettoyer_json(raw))
    except Exception as e:
        return {"erreur": f"JSON invalide: {e}", "raw": raw[:300]}

    plan = data.get("sous_taches", [])
    if not isinstance(plan, list) or not plan:
        return {"erreur": "plan vide", "raw": raw[:300]}

    ids = []
    for st in plan:
        agent = st.get("agent", "01_developpeur")
        if agent not in PERMISSIONS_AGENTS:
            agent = "01_developpeur"
        objectif = str(st.get("objectif", "")).strip()
        if not objectif:
            ids.append(None)
            continue
        deps_idx = st.get("dependances", []) or []
        deps_ids = [ids[d] for d in deps_idx
                    if isinstance(d, int) and 0 <= d < len(ids) and ids[d]]
        try:
            created = mm.ajouter_sous_tache(mission_id, agent, objectif, deps_ids)
            ids.append(created["id"])
        except Exception:
            ids.append(None)

    return {"ok": True, "nb": len([i for i in ids if i]), "ids": ids}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m core.mission_planner <mission_id>")
        sys.exit(1)
    print(json.dumps(planifier(sys.argv[1]), indent=2, ensure_ascii=False))
