class EventManager:
    def __init__(self):
        self.evenements = {}

    def enregistrer(self, nom, fonction):
        if nom not in self.evenements:
            self.evenements[nom] = []

        self.evenements[nom].append(fonction)

    def declencher(self, nom, donnees=None):
        if nom in self.evenements:
            for fonction in self.evenements[nom]:
                fonction(donnees)
