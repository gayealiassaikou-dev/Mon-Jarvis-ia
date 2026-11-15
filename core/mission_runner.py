"""
Executeur manuel de missions.
Usage : python -m core.mission_runner --max 3
Mode manuel uniquement : l'utilisateur declenche.
"""
import argparse
import sys

from core.mission_manager import MissionManager
from core.coordination_manager import CoordinationManager
from core.logger import Logger


def executer(max_missions=1, dry_run=False):
    logger = Logger()
    mm = MissionManager()
    coord = CoordinationManager(mm, logger)

    missions = mm.missions_a_reprendre()
    if not missions:
        print("Aucune mission a reprendre.")
        return 0

    print(f"{len(missions)} mission(s) en attente. Max: {max_missions}")
    traitees = 0

    for m in missions[:max_missions]:
        mid = m["id"]
        nom = m["nom"]
        print(f"\n=== Mission {mid} : {nom[:80]} ===")

        if dry_run:
            print(f"[DRY-RUN] Serait executee (statut actuel: {m['statut']})")
            traitees += 1
            continue

        try:
            sous_taches = mm.obtenir_sous_taches(mid)
            if not sous_taches:
                print(f"[Planner] Decomposition de {mid}...")
                from core.mission_planner import planifier
                plan = planifier(mid)
                if plan.get("ok"):
                    print(f"[Planner] {plan['nb']} sous-taches creees.")
                else:
                    print(f"[Planner] Echec ({plan.get('erreur')}), execution directe.")

            sous_taches = mm.obtenir_sous_taches(mid)
            if sous_taches:
                from core.subtask_executor import executer_mission
                res = executer_mission(mid)
                if res.get("ok"):
                    print(f"[OK] Mission {mid} terminee via sous-taches ({res.get('etapes')} etapes).")
                    traitees += 1
                else:
                    print(f"[ECHEC] Mission {mid} : {res.get('statut')}")
            else:
                from core.jarvis import Jarvis
                j = Jarvis()
                reponse = j.traiter_commande(nom, retourner_reponse=True)
                if reponse and isinstance(reponse, str):
                    mm.mettre_a_jour_statut(mid, "terminee")
                    print(f"[OK] Mission {mid} terminee (directe).")
                    traitees += 1
                else:
                    print(f"[ECHEC] Reponse vide pour {mid}.")
        except Exception as e:
            print(f"[ERREUR] {mid} : {type(e).__name__}: {e}")
            try:
                mm.mettre_a_jour_statut(mid, "bloquee")
            except Exception:
                pass
        finally:
            # Incrementer les tentatives ; abandonner si > 3
            try:
                mission = mm.obtenir_mission(mid)
                if mission and mission.get("statut") in ("bloquee", "en_cours"):
                    tentatives = int(mission.get("tentatives", 0)) + 1
                    donnees = mm._charger()
                    for mmis in donnees["missions"]:
                        if mmis["id"] == mid:
                            mmis["tentatives"] = tentatives
                            if tentatives >= 3:
                                mmis["statut"] = "annulee"
                                mmis["abandonnee"] = True
                                print(f"[ABANDON] {mid} apres {tentatives} tentatives")
                            break
                    mm._sauvegarder(donnees)
            except Exception as e2:
                print(f"[ERR tentative] {e2}")

    print(f"\nTotal traitees : {traitees}")
    return traitees


def boucle_watch(intervalle=60, max_par_cycle=3):
    """Boucle de fond : traite les missions + verifie les triggers."""
    import time
    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n[Cycle {cycle}] {time.strftime('%H:%M:%S')}")

            # 1. Verifier les triggers (timer, fichier)
            try:
                from core.trigger_engine import verifier_et_executer
                nt = verifier_et_executer(max_executions=3)
                if nt:
                    print(f"[Triggers] {nt} mission(s) creee(s)")
            except Exception as e:
                print(f"[ERREUR TRIGGERS] {type(e).__name__}: {e}")

            # 2. Executer les missions pretes
            try:
                n = executer(max_missions=max_par_cycle, dry_run=False)
                if n == 0:
                    print(f"Rien a faire. Sommeil {intervalle}s...")
            except Exception as e:
                print(f"[ERREUR CYCLE] {type(e).__name__}: {e}")
            time.sleep(intervalle)
    except KeyboardInterrupt:
        print("\n[Arret propre] Boucle terminee.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Boucle de fond")
    parser.add_argument("--intervalle", type=int, default=60, help="Secondes entre cycles")
    args = parser.parse_args()

    if args.watch:
        boucle_watch(intervalle=args.intervalle, max_par_cycle=args.max)
    else:
        executer(max_missions=args.max, dry_run=args.dry_run)
