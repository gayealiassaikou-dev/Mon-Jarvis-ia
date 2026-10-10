import os


class KnowledgeManager:
    def __init__(self):
        self.connaissances = {}
        self.charger_connaissances()

    def charger_connaissances(self):
        dossier = "knowledge"

        if not os.path.exists(dossier):
            os.makedirs(dossier)

        for fichier in os.listdir(dossier):
            if fichier.endswith(".md"):
                nom = fichier.replace(".md", "")
                
                chemin = os.path.join(dossier, fichier)

                with open(chemin, "r", encoding="utf-8") as f:
                    self.connaissances[nom] = f.read()

    def afficher_connaissances(self):
        print("Base de connaissances :")

        for connaissance in self.connaissances:
            print("-", connaissance)
