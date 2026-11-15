"""Execute les sous-taches pretes d'une mission, dans l'ordre des dependances."""
from core.mission_manager import MissionManager


def _pretes(sous_taches, statut_map):
    pretes = []
    for st in sous_taches:
        if st["statut"] != "nouvelle":
            continue
        deps = st.get("dependances", [])
        if all(statut_map.get(d) == "terminee" for d in deps):
            pretes.append(st)
    return pretes


def executer_mission(mission_id, max_etapes=10, auto_planifier=True):
    from core.jarvis import Jarvis
    mm = MissionManager()
    mission = mm.obtenir_mission(mission_id)
    if not mission:
        return {"erreur": "mission introuvable"}

    # Auto-planification : si la mission n'a aucune sous-tache,
    # on la decompose automatiquement avant execution.
    if auto_planifier and not mm.obtenir_sous_taches(mission_id):
        print(f"[Auto-planner] Decomposition de {mission_id}...")
        try:
            from core.mission_planner import planifier
            plan = planifier(mission_id)
            if not plan.get("ok"):
                return {
                    "erreur": f"planification echouee: {plan.get('erreur', 'inconnue')}",
                    "statut": "planification_echouee",
                }
            print(f"[Auto-planner] {plan.get('nb', 0)} sous-tache(s) creee(s).")
        except Exception as e:
            return {"erreur": f"planner exception: {type(e).__name__}: {e}"}

    jarvis = Jarvis()
    etapes = 0

    for _ in range(max_etapes):
        sous_taches = mm.obtenir_sous_taches(mission_id)
        if not sous_taches:
            return {"erreur": "aucune sous-tache apres planification", "statut": "vide"}

        statut_map = {st["id"]: st["statut"] for st in sous_taches}
        if all(s == "terminee" for s in statut_map.values()):
            mm.mettre_a_jour_statut(mission_id, "terminee")
            return {"ok": True, "etapes": etapes, "statut": "terminee"}

        pretes = _pretes(sous_taches, statut_map)
        if not pretes:
            bloquee = [s for s in statut_map.values() if s == "bloquee"]
            if bloquee:
                mm.mettre_a_jour_statut(mission_id, "bloquee")
                return {"ok": False, "statut": "bloquee", "etapes": etapes}
            return {"ok": False, "statut": "deadlock", "etapes": etapes}

        st = pretes[0]
        print(f"\n[Sous-tache {st['id']}] {st['agent']} : {st['objectif'][:80]}")
        mm.mettre_a_jour_sous_tache(mission_id, st["id"], "en_cours")

        try:
            # 1. Tentative deterministe (sans LLM) pour actions simples
            from core import deterministic_actions
            det = deterministic_actions.tenter(st["objectif"])
            if det and det.get("ok"):
                reponse = det.get("message", "OK")
                nouveaux_outils = [{"outil": det.get("outil"), "statut": "succes", "execute": True}]
                print(f"[Deterministe] {det.get('outil')} execute sans LLM")
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "terminee", resultat=reponse[:500])
                print(f"[OK] {st['id']} (deterministe)")
                etapes += 1
                continue
            # 2. Sinon, pipeline LLM classique (avec conseils d'apprentissage)
            from core import learning as _learning
            objectif_enrichi = st["objectif"]
            conseils = _learning.conseils_pour(st["objectif"])
            if conseils:
                objectif_enrichi = st["objectif"] + conseils
                print(f"[Apprentissage] {conseils.count(chr(10)) - 2} conseil(s) injecte(s)")
            resultats_avant = len(jarvis.ai_engine.derniers_resultats_outils)
            reponse = jarvis.traiter_commande(objectif_enrichi, retourner_reponse=True, agent_force=st["agent"])
            nouveaux_outils = jarvis.ai_engine.derniers_resultats_outils[resultats_avant:]
            SIGNES_ECHEC = [
                "validation echouee", "je n'ai pas pu confirmer",
                "erreur ia", "aucun outil execute",
                "reussite non prouvee", "action(s) en echec",
                "je ne peux pas", "je ne suis pas en mesure",
                "que souhaitez-vous", "voulez-vous que je",
                "a votre confirmation", "quel scenario",
                "quelle option", "je ne lancerai aucune modification",
                "voulez-vous", "souhaitez-vous", "voulez vous",
                "confirmez", "attendez confirmation",
                "attends votre confirmation", "attend votre confirmation",
                "attendre votre confirmation", "j'attends votre confirmation",
                "en attente de confirmation", "avant d'agir",
                "je peux :", "je peux\u00a0:",
            ]
            # Si l'objectif demande une action concrete, la reponse doit contenir
            # une preuve d'action (pas juste du texte theorique)
            import unicodedata as _uni
            def _norm(t):
                return "".join(c for c in _uni.normalize("NFKD", str(t).lower()) if not _uni.combining(c))
            objectif_norm = _norm(st["objectif"])
            # Actions concretes qui exigent OBLIGATOIREMENT un outil
            MOTS_ACTION_CONCRETE = [
                # Fichiers
                "ecri", "cree", "creer", "modifie", "supprime",
                # Execution
                "execute", "executer", "lance", "lancer", "run",
                # Depot / installation
                "depot", "repo", "push", "commit", "installe", "telecharge",
                # Dev / implementation
                "developp", "implement", "programme", "realise", "construi",
                "genere", "produis", "code", "script",
            ]
            MOTS_RESPONSE_INFO = [
                "calcule", "calculer", "combien", "quel est", "quelle est",
                "explique", "explication", "analyse", "compare", "difference",
                "resume", "decris", "liste", "donne moi le resultat", "theorique",
            ]
            est_action_concrete = any(w in objectif_norm for w in MOTS_ACTION_CONCRETE)
            est_response_info = any(w in objectif_norm for w in MOTS_RESPONSE_INFO)
            # Forcer outil UNIQUEMENT si action concrete ET pas une simple demande de calcul/expli
            demande_action = est_action_concrete and not (
                est_response_info and not any(w in objectif_norm for w in ["ecris", "ecrire", "cree le fichier", "creer le fichier", "cree un fichier"])
            )
            rep_str = str(reponse or "").lower()
            a_repondu_texte_long = rep_str.count("\n") > 15 or len(rep_str) > 2000
            theorique_sans_action = demande_action and a_repondu_texte_long and not any(
                signe in rep_str for signe in ["fichier", "cree", "ecrit", "termine avec", "succes"]
            )
            # Reponse qui ne fait que repeter le system prompt ou le nom de l'agent
            repete_prompt = (
                len(rep_str) < 150
                and any(x in rep_str for x in ["testeur ia :", "developpeur ia :", "recherche ia :", "verifier la qualite"])
            )
            est_echec = (
                not reponse
                or not isinstance(reponse, str)
                or len(reponse.strip()) < 5
                or repete_prompt
                or any(sig in rep_str for sig in SIGNES_ECHEC)
                or theorique_sans_action
                or (demande_action and not nouveaux_outils)
            )
            # Sauvegarde reponse originale (peut contenir du code a extraire)
            reponse_originale = reponse

            # Detecter JSON action ou bloc code AVANT retry (economie quota)
            _reponse_a_code = False
            _rep_pre = str(reponse or "")
            if _rep_pre:
                if '"action"' in _rep_pre and '"parameters"' in _rep_pre:
                    _reponse_a_code = True
                elif "```python" in _rep_pre or "```" in _rep_pre:
                    _reponse_a_code = True

            # Retry force uniquement si pas de code/JSON exploitable
            if est_echec and demande_action and not nouveaux_outils and not _reponse_a_code:
                print(f"[Retry force] {st['id']} : aucun outil, on force")
                # Enrichir le retry avec les conseils d'apprentissage
                conseils_retry = ""
                try:
                    from core import learning as _learning_retry
                    _c = _learning_retry.conseils_pour(st["objectif"])
                    if _c:
                        conseils_retry = _c
                        print(f"[Retry force] + conseils d'apprentissage injectes")
                except Exception:
                    pass

                message_force = (
                    f"APPEL D'OUTIL OBLIGATOIRE. Tu dois appeler l'outil adapte pour : "
                    f"{st['objectif']}. Ne reponds pas en texte. Ne décris pas. "
                    f"Appelle directement `ecrire_fichier` (chemin + contenu) ou "
                    f"`executer_programme_python`. C'est la seule action acceptee."
                    + conseils_retry
                )
                try:
                    avant2 = len(jarvis.ai_engine.derniers_resultats_outils)
                    reponse = jarvis.traiter_commande(message_force, retourner_reponse=True, agent_force=st["agent"])
                    nouveaux_outils = jarvis.ai_engine.derniers_resultats_outils[avant2:]
                    rep_str = str(reponse or "").lower()
                    est_echec = (
                        not reponse
                        or not isinstance(reponse, str)
                        or len(reponse.strip()) < 5
                        or any(sig in rep_str for sig in SIGNES_ECHEC)
                        or (demande_action and not nouveaux_outils)
                    )
                    print(f"[Retry force] outils appeles: {len(nouveaux_outils)}, echec={est_echec}")
                except Exception as e2:
                    print(f"[Retry force ERREUR] {e2}")

            # Fallback final : extraire code Python ou JSON d'action
            if est_echec and demande_action:
                import re as _re
                import json as _json
                sources = [str(reponse or ""), str(reponse_originale or "")]

                # 1. Detecter JSON {"action": "nom_outil", "parameters": {...}}
                for src in sources:
                    try:
                        m_json = _re.search(r'\{[^{}]*"action"\s*:\s*"([^"]+)"[^{}]*"parameters"\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})[^{}]*\}', src, _re.DOTALL)
                        if not m_json:
                            # Variante : chercher le premier { ... } equilibre
                            start = src.find('{')
                            if start >= 0:
                                depth = 0
                                for i in range(start, len(src)):
                                    if src[i] == '{': depth += 1
                                    elif src[i] == '}':
                                        depth -= 1
                                        if depth == 0:
                                            candidate = src[start:i+1]
                                            try:
                                                obj = _json.loads(candidate)
                                                if isinstance(obj, dict) and "action" in obj:
                                                    m_json = True
                                                    nom_outil = obj.get("action")
                                                    params = obj.get("parameters", {})
                                                    from core.tools import (
                                                        ecrire_fichier as _ef, lire_fichier as _lf,
                                                        creer_dossier as _cd, supprimer_fichier as _sf,
                                                        executer_programme_python as _ep,
                                                    )
                                                    mapping = {
                                                        "ecrire_fichier": _ef, "lire_fichier": _lf,
                                                        "creer_dossier": _cd, "supprimer_fichier": _sf,
                                                        "executer_script": None,  # traite plus bas
                                                        "executer_programme_python": _ep,
                                                        "executer_script_python": None,
                                                    }
                                                    if nom_outil == "executer_script" or nom_outil == "executer_script_python":
                                                        # Le LLM renvoie du code Python a executer directement
                                                        code_script = params.get("script", "") or params.get("code", "")
                                                        if code_script:
                                                            # Le script tourne DEJA dans espace_travail/ (cwd)
                                                            code_script = code_script.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
                                                            tmp_chemin = f"espace_travail/_e2e_{__import__('uuid').uuid4().hex[:8]}.py"
                                                            _ef(tmp_chemin, code_script + "\n")
                                                            res = _ep(tmp_chemin)
                                                            print(f"[Fallback JSON] executer_script -> {str(res)[:150]}")
                                                            if "code 0" in str(res).lower() or "succes" in str(res).lower():
                                                                est_echec = False
                                                            reponse = f"Script execute: {str(res)[:400]}"
                                                            break
                                                    elif nom_outil in mapping and mapping[nom_outil] is not None:
                                                        # Nettoyer le contenu si c'est un .py
                                                        if nom_outil == "ecrire_fichier" and str(params.get("chemin", "")).endswith(".py"):
                                                            contenu_brut = params.get("contenu", "")
                                                            params["contenu"] = contenu_brut.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
                                                        res = mapping[nom_outil](**params)
                                                        print(f"[Fallback JSON] {nom_outil} execute: {str(res)[:150]}")
                                                        est_echec = False
                                                        reponse = f"Outil {nom_outil} execute: {str(res)[:300]}"
                                                    break
                                            except Exception:
                                                pass
                                    if m_json: break
                        if m_json and isinstance(m_json, _re.Match):
                            nom_outil = m_json.group(1)
                            params = _json.loads(m_json.group(2))
                            from core.tools import (
                                ecrire_fichier as _ef, lire_fichier as _lf,
                                creer_dossier as _cd, supprimer_fichier as _sf,
                                executer_programme_python as _ep,
                            )
                            mapping = {
                                "ecrire_fichier": _ef, "lire_fichier": _lf,
                                "creer_dossier": _cd, "supprimer_fichier": _sf,
                                "executer_programme_python": _ep,
                            }
                            if nom_outil in ("executer_script", "executer_script_python"):
                                code_script = params.get("script", "") or params.get("code", "")
                                if code_script:
                                    code_script = code_script.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
                                    import uuid as _uuid
                                    tmp_chemin = f"espace_travail/_e2e_{_uuid.uuid4().hex[:8]}.py"
                                    _ef(tmp_chemin, code_script + "\n")
                                    res = _ep(tmp_chemin)
                                    print(f"[Fallback JSON] executer_script -> {str(res)[:150]}")
                                    if "code 0" in str(res).lower() or "succes" in str(res).lower():
                                        est_echec = False
                                    reponse = f"Script execute: {str(res)[:400]}"
                                    break
                            elif nom_outil in mapping:
                                # Nettoyer le contenu si c'est un .py
                                if nom_outil == "ecrire_fichier" and str(params.get("chemin", "")).endswith(".py"):
                                    contenu_brut = params.get("contenu", "")
                                    params["contenu"] = contenu_brut.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
                                res = mapping[nom_outil](**params)
                                print(f"[Fallback JSON] {nom_outil} execute: {str(res)[:150]}")
                                # Executer le .py si c'est un script
                                if nom_outil == "ecrire_fichier" and str(params.get("chemin", "")).endswith(".py"):
                                    try:
                                        sortie = _ep(params["chemin"])
                                        print(f"[Fallback JSON] Execution {params['chemin']}: {str(sortie)[:150]}")
                                        res = f"{res} | Execution: {str(sortie)[:200]}"
                                    except Exception as _e2:
                                        print(f"[Fallback JSON] Execution echouee: {_e2}")
                                est_echec = False
                                reponse = f"Outil {nom_outil} execute: {str(res)[:400]}"
                                break
                    except Exception:
                        pass

                blocs = []
                if est_echec:
                    # 2. Fallback classique : extraire code Python
                    for src in sources:
                        blocs.extend(_re.findall(r"```(?:python)?\s*\n(.+?)```", src, _re.DOTALL))
                if blocs:
                    code = max(blocs, key=len).strip()
                    # Le script tourne DEJA dans espace_travail/ (cwd).
                    # Retirer le prefixe "espace_travail/" pour eviter un sous-dossier.
                    code = code.replace("espace_travail/", "").replace('espace_travail"', '"')
                    from core.tools import ecrire_fichier as _ecrire, executer_programme_python as _exec
                    chemin = f"espace_travail/sous_tache_{st['id']}.py"
                    try:
                        _ecrire(chemin, code + "\n")
                        print(f"[Fallback] Code extrait dans {chemin}")
                        sortie = _exec(chemin)
                        print(f"[Fallback] Execution: {str(sortie)[:200]}")
                        est_echec = False
                        reponse = f"Code ecrit dans {chemin} et execute. Sortie: {str(sortie)[:300]}"
                    except Exception as e3:
                        print(f"[Fallback ERREUR] {e3}")

            if not est_echec:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "terminee", resultat=reponse[:500])
                try:
                    from core import learning as _learning
                    _learning.enregistrer_solution(st["objectif"], reponse[:300], st["agent"])
                except Exception:
                    pass
                print(f"[OK] {st['id']}")
            else:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "bloquee", resultat=str(reponse)[:500])
                try:
                    from core import learning as _learning
                    _learning.enregistrer_echec(st["objectif"], str(reponse)[:200], st["agent"])
                except Exception:
                    pass
                print(f"[ECHEC] {st['id']} : validation reelle echouee")
                mm.mettre_a_jour_statut(mission_id, "bloquee")
                return {"ok": False, "statut": "bloquee", "etapes": etapes + 1, "echec_sur": st["id"]}
        except Exception as e:
            print(f"[ERREUR] {st['id']}: {type(e).__name__}: {e}")
            try:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "bloquee", resultat=str(e)[:200])
            except Exception:
                pass
            mm.mettre_a_jour_statut(mission_id, "bloquee")
            return {"ok": False, "statut": "exception", "etapes": etapes + 1, "echec_sur": st["id"]}

        etapes += 1

    return {"ok": False, "statut": "max_etapes", "etapes": etapes}


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python -m core.subtask_executor <mission_id>")
        sys.exit(1)
    print(json.dumps(executer_mission(sys.argv[1]), indent=2, ensure_ascii=False))
