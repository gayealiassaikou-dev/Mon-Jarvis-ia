class ContextManager:
    def __init__(self):
        self.contexte = {}

    def definir(self, cle, valeur):
        self.contexte[cle] = valeur

    def obtenir(self, cle):
        return self.contexte.get(cle)

    def afficher(self):
        print("Contexte actuel :")

        for cle, valeur in self.contexte.items():
            print("-", cle, ":", valeur)
