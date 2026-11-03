import json
import os
import uuid
from datetime import datetime

CHEMIN_MISSIONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "missions.json")

STATUTS_VALIDES = ["nouvelle", "en_cours", "terminee", "bloquee", "annulee"]
PRIORITES_VALIDES = ["critique", "haute", "normale", "faible"]


class MissionManager:

    def __init__(self):
        self.chemin = CHEMIN_MISSIONS
        self._initialiser_fichier()

    def _initialiser_fichier(self):
        if not os.path.exists(self.chemin):
            os.makedirs(os.path.dirname(self.chemin), exist_ok=True)
            with open(self.chemin, "w", encoding="utf-8") as f:
                json.dump({"missions": []}, f, indent=4, ensure_ascii=False)

    def _charger(self):
        with open(self.chemin, "r", encoding="utf-8") as f:
            return json.load(f)

    def _sauvegarder(self, donnees):
        with open(self.chemin, "w", encoding="utf-8") as f:
            json.dump(donnees, f, indent=4, ensure_ascii=False)

    def creer_mission(self, nom, objectif="", agents=None, priorite="normale"):
        if priorite not in PRIORITES_VALIDES:
            priorite = "normale"

        mission = {
            "id": str(uuid.uuid4())[:8],
            "nom": nom,
            "objectif": objectif,
            "agents": agents if agents else [],
            "sous_taches": [],
            "priorite": priorite,
            "statut": "nouvelle",
            "date_creation": datetime.now().isoformat(timespec="seconds"),
            "date_maj": datetime.now().isoformat(timespec="seconds")
        }

        donnees = self._charger()
        donnees["missions"].append(mission)
        self._sauvegarder(donnees)
        return mission

    def mettre_a_jour_statut(self, mission_id, nouveau_statut):
        transitions_autorisees = {
            "nouvelle": {"en_cours", "annulee"},
            "en_cours": {"terminee", "bloquee", "annulee"},
            "bloquee": {"en_cours", "annulee"},
            "terminee": set(),
            "annulee": set(),
        }

        if nouveau_statut not in STATUTS_VALIDES:
            return f"Statut invalide. Statuts possibles : {', '.join(STATUTS_VALIDES)}"

        donnees = self._charger()
        for mission in donnees["missions"]:
            if mission["id"] == mission_id:
                statut_actuel = mission.get("statut")

                if nouveau_statut == statut_actuel:
                    return f"Mission {mission_id} deja au statut : {statut_actuel}"

                autorises = transitions_autorisees.get(statut_actuel, set())
                if nouveau_statut not in autorises:
                    return (
                        f"Transition refusee pour la mission {mission_id} : "
                        f"{statut_actuel} -> {nouveau_statut}."
                    )

                mission["statut"] = nouveau_statut
                mission["date_maj"] = datetime.now().isoformat(timespec="seconds")
                self._sauvegarder(donnees)
                return f"Mission {mission_id} mise a jour : {nouveau_statut}"

        return f"Mission {mission_id} introuvable."

    def obtenir_mission(self, mission_id):
        donnees = self._charger()
        for mission in donnees["missions"]:
            if mission["id"] == mission_id:
                return mission
        return None

    def lister_missions(self, statut=None):
        donnees = self._charger()
        missions = donnees["missions"]
        if statut:
            missions = [m for m in missions if m["statut"] == statut]
        return missions

    def ajouter_sous_tache(
        self, mission_id, agent, objectif, dependances=None
    ):
        if not isinstance(agent, str) or not agent.strip():
            raise ValueError("Un agent valide est obligatoire.")
        if not isinstance(objectif, str) or not objectif.strip():
            raise ValueError("Un objectif valide est obligatoire.")

        if dependances is None:
            dependances = []
        if not isinstance(dependances, list):
            raise ValueError("Les dependances doivent etre une liste.")
        if len(dependances) != len(set(dependances)):
            raise ValueError("Une dependance ne peut pas etre repetee.")

        donnees = self._charger()
        for mission in donnees["missions"]:
            if mission["id"] != mission_id:
                continue

            sous_taches = mission.setdefault("sous_taches", [])
            ids_existants = {t["id"] for t in sous_taches}

            if any(dep not in ids_existants for dep in dependances):
                raise ValueError(
                    "Une dependance indiquee est introuvable dans cette mission."
                )

            sous_tache = {
                "id": str(uuid.uuid4())[:8],
                "agent": agent.strip(),
                "objectif": objectif.strip(),
                "statut": "nouvelle",
                "dependances": list(dependances),
                "resultat": None,
                "date_creation": datetime.now().isoformat(timespec="seconds"),
                "date_maj": datetime.now().isoformat(timespec="seconds"),
            }

            sous_taches.append(sous_tache)
            self._sauvegarder(donnees)
            return sous_tache

        raise ValueError(f"Mission {mission_id} introuvable.")

    def obtenir_sous_taches(self, mission_id):
        donnees = self._charger()
        for mission in donnees["missions"]:
            if mission["id"] == mission_id:
                return mission.get("sous_taches", [])
        return []

    def mettre_a_jour_sous_tache(
        self, mission_id, sous_tache_id, nouveau_statut, resultat=None
    ):
        statuts = ["nouvelle", "en_cours", "terminee", "bloquee", "annulee"]
        transitions = {
            "nouvelle": {"en_cours", "annulee"},
            "en_cours": {"terminee", "bloquee", "annulee"},
            "bloquee": {"en_cours", "annulee"},
            "terminee": set(),
            "annulee": set(),
        }

        if nouveau_statut not in statuts:
            return f"Statut invalide. Statuts possibles : {', '.join(statuts)}"

        donnees = self._charger()
        for mission in donnees["missions"]:
            if mission["id"] != mission_id:
                continue

            sous_taches = mission.get("sous_taches", [])
            for sous_tache in sous_taches:
                if sous_tache["id"] != sous_tache_id:
                    continue

                statut_actuel = sous_tache["statut"]
                if nouveau_statut == statut_actuel:
                    return f"Sous-tache deja au statut : {statut_actuel}"

                if nouveau_statut not in transitions.get(statut_actuel, set()):
                    return (
                        f"Transition refusee : {statut_actuel} "
                        f"-> {nouveau_statut}."
                    )

                if nouveau_statut in {"en_cours", "terminee"}:
                    par_id = {t["id"]: t for t in sous_taches}
                    non_terminees = [
                        dep for dep in sous_tache.get("dependances", [])
                        if dep not in par_id
                        or par_id[dep].get("statut") != "terminee"
                    ]
                    if non_terminees:
                        return (
                            "Transition refusee : les dependances doivent "
                            "etre terminees avant cette sous-tache."
                        )

                sous_tache["statut"] = nouveau_statut
                if resultat is not None:
                    sous_tache["resultat"] = resultat
                sous_tache["date_maj"] = datetime.now().isoformat(
                    timespec="seconds"
                )
                self._sauvegarder(donnees)
                return (
                    f"Sous-tache {sous_tache_id} mise a jour : "
                    f"{nouveau_statut}"
                )

            return f"Sous-tache {sous_tache_id} introuvable."

        return f"Mission {mission_id} introuvable."

    def afficher_missions(self):
        missions = self.lister_missions()
        if not missions:
            print("Aucune mission enregistree.")
            return
        print("Missions :")
        for m in missions:
            print(f"- [{m['id']}] {m['nom']} ({m['statut']}, priorite: {m['priorite']})")
