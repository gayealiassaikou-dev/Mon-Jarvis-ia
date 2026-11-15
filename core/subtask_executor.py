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


def executer_mission(mission_id, max_etapes=10):
    from core.jarvis import Jarvis
    mm = MissionManager()
    mission = mm.obtenir_mission(mission_id)
    if not mission:
        return {"erreur": "mission introuvable"}

    jarvis = Jarvis()
    etapes = 0

    for _ in range(max_etapes):
        sous_taches = mm.obtenir_sous_taches(mission_id)
        if not sous_taches:
            return {"erreur": "aucune sous-tache"}

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
            est_echec = (
                not reponse
                or not isinstance(reponse, str)
                or len(reponse.strip()) < 5
                or any(sig in rep_str for sig in SIGNES_ECHEC)
                or theorique_sans_action
                or (demande_action and not nouveaux_outils)
            )
            # Retry force si aucun outil n'a ete appele
            if est_echec and demande_action and not nouveaux_outils:
                print(f"[Retry force] {st['id']} : aucun outil, on force")
                message_force = (
                    f"APPEL D'OUTIL OBLIGATOIRE. Tu dois appeler l'outil adapte pour : "
                    f"{st['objectif']}. Ne reponds pas en texte. Ne décris pas. "
                    f"Appelle directement `ecrire_fichier` (chemin + contenu) ou "
                    f"`executer_programme_python`. C'est la seule action acceptee."
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
