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
            from core.jarvis import Jarvis
            j = Jarvis()
            reponse = j.traiter_commande(nom, retourner_reponse=True)
            if reponse and isinstance(reponse, str):
                mm.mettre_a_jour_statut(mid, "terminee")
                print(f"[OK] Mission {mid} terminee.")
                traitees += 1
            else:
                print(f"[ECHEC] Reponse vide pour {mid}.")
        except Exception as e:
            print(f"[ERREUR] {mid} : {type(e).__name__}: {e}")
            try:
                mm.mettre_a_jour_statut(mid, "bloquee")
            except Exception:
                pass

    print(f"\nTotal traitees : {traitees}")
    return traitees


def boucle_watch(intervalle=60, max_par_cycle=3):
    """Boucle de fond : traite les missions, dort, recommence."""
    import time
    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n[Cycle {cycle}] {time.strftime('%H:%M:%S')}")
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
