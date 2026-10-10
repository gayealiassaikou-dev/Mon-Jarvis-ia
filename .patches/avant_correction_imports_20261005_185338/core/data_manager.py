import json
import os


class DataManager:
    def __init__(self):
        self.dossier = "data"

        if not os.path.exists(self.dossier):
            os.makedirs(self.dossier)

    def sauvegarder(self, nom, donnees):
        chemin = os.path.join(self.dossier, nom)

        with open(chemin, "w", encoding="utf-8") as fichier:
            json.dump(donnees, fichier, indent=4, ensure_ascii=False)

    def charger(self, nom):
        chemin = os.path.join(self.dossier, nom)

        if not os.path.exists(chemin):
            return None

        with open(chemin, "r", encoding="utf-8") as fichier:
            return json.load(fichier)
