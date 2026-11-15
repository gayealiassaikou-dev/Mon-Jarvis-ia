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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    executer(max_missions=args.max, dry_run=args.dry_run)
