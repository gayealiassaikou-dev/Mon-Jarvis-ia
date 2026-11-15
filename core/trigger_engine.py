"""Moteur de declenchement - verifie les triggers et execute les missions."""
import os
import time
from datetime import datetime

from core import triggers


def _intervalle_ecoule(trigger):
    derniere = trigger.get("derniere_execution")
    if not derniere:
        return True
    try:
        d = datetime.fromisoformat(derniere)
    except Exception:
        return True
    ecart = (datetime.now() - d).total_seconds() / 60.0
    return ecart >= trigger["intervalle_minutes"]


def _fichier_change(trigger):
    chemin = trigger.get("chemin_surveille")
    if not chemin or not os.path.exists(chemin):
        return False
    mtime_actuel = os.path.getmtime(chemin)
    mtime_connu = trigger.get("dernier_mtime")
    if mtime_connu is None:
        return True
    return mtime_actuel > mtime_connu


def verifier_et_executer(max_executions=3):
    """Verifie tous les triggers actifs, execute ceux qui sont dus. Retourne le nombre executes."""
    executes = 0
    for t in triggers.lister():
        if not t.get("actif"):
            continue
        if executes >= max_executions:
            break

        du = False
        if t["type"] == "timer":
            du = _intervalle_ecoule(t)
        elif t["type"] == "fichier":
            du = _fichier_change(t)

        if not du:
            continue

        print(f"[TRIGGER] {t['id']} ({t['type']}) -> {t['mission_nom'][:60]}")
        try:
            from core.mission_manager import MissionManager
            mm = MissionManager()
            mission = mm.creer_mission(
                nom=t["mission_nom"],
                objectif=f"Declenche par trigger {t['id']} ({t['type']})",
                priorite="normale",
            )
            mm.mettre_a_jour_statut(mission["id"], "en_cours")
            triggers.marquer_execute(t["id"])
            executes += 1
            print(f"[TRIGGER] Mission {mission['id']} creee")
        except Exception as e:
            print(f"[TRIGGER ERREUR] {type(e).__name__}: {e}")

    return executes


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--intervalle", type=int, default=60)
    args = parser.parse_args()

    if args.watch:
        print(f"[TRIGGERS] Boucle demarree (verif toutes les {args.intervalle}s)")
        try:
            while True:
                n = verifier_et_executer()
                if n:
                    print(f"[TRIGGERS] {n} mission(s) creee(s)")
                time.sleep(args.intervalle)
        except KeyboardInterrupt:
            print("\n[TRIGGERS] Arret.")
    else:
        n = verifier_et_executer()
        print(f"Total execute: {n}")
