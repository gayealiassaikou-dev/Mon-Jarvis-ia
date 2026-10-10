import os


class BrainManager:
    def __init__(self):
        self.connaissances = {}
        self.charger_brain()

    def charger_brain(self):
        dossier = "brain"

        for fichier in os.listdir(dossier):
            if fichier.endswith(".md"):
                nom = fichier.replace(".md", "")
                chemin = os.path.join(dossier, fichier)

                with open(chemin, "r", encoding="utf-8") as f:
                    self.connaissances[nom] = f.read()

    def afficher_brain(self):
        print("Connaissances du cerveau :")

        for connaissance in self.connaissances:
            print("-", connaissance)
