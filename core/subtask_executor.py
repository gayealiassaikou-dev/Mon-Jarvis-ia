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
            reponse = jarvis.traiter_commande(st["objectif"], retourner_reponse=True, agent_force=st["agent"])
            SIGNES_ECHEC = [
                "validation echouee", "je n'ai pas pu confirmer",
                "erreur ia", "aucun outil execute",
                "reussite non prouvee", "action(s) en echec",
            ]
            rep_str = str(reponse or "").lower()
            est_echec = (
                not reponse
                or not isinstance(reponse, str)
                or len(reponse.strip()) < 5
                or any(sig in rep_str for sig in SIGNES_ECHEC)
            )
            if not est_echec:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "terminee", resultat=reponse[:500])
                print(f"[OK] {st['id']}")
            else:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "bloquee", resultat=str(reponse)[:500])
                print(f"[ECHEC] {st['id']} : validation reelle echouee")
        except Exception as e:
            mm.mettre_a_jour_sous_tache(mission_id, st["id"], "bloquee", resultat=str(e)[:200])
            print(f"[ERREUR] {st['id']}: {type(e).__name__}: {e}")

        etapes += 1

    return {"ok": False, "statut": "max_etapes", "etapes": etapes}


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python -m core.subtask_executor <mission_id>")
        sys.exit(1)
    print(json.dumps(executer_mission(sys.argv[1]), indent=2, ensure_ascii=False))
