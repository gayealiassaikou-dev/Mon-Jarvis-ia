import os


class BrainLoader:

    def __init__(self):
        self.chemin_brain = "brain"
        self.connaissances = {}

    def charger(self):
        if not os.path.exists(self.chemin_brain):
            return False

        for fichier in os.listdir(self.chemin_brain):

            if fichier.endswith(".md"):
                chemin = os.path.join(
                    self.chemin_brain,
                    fichier
                )

                with open(
                    chemin,
                    "r",
                    encoding="utf-8"
                ) as f:
                    self.connaissances[fichier] = f.read()

        return True

    def afficher(self):
        print("Cerveau chargé :")

        for fichier in self.connaissances:
            print("-", fichier)
