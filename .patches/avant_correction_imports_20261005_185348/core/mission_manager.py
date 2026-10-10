import json
import os
import uuid
from datetime import datetime

CHEMIN_MISSIONS = os.path.join("data", "missions.json")

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
        if nouveau_statut not in STATUTS_VALIDES:
            return f"Statut invalide. Statuts possibles : {', '.join(STATUTS_VALIDES)}"

        donnees = self._charger()
        for mission in donnees["missions"]:
            if mission["id"] == mission_id:
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

    def afficher_missions(self):
        missions = self.lister_missions()
        if not missions:
            print("Aucune mission enregistree.")
            return
        print("Missions :")
        for m in missions:
            print(f"- [{m['id']}] {m['nom']} ({m['statut']}, priorite: {m['priorite']})")
