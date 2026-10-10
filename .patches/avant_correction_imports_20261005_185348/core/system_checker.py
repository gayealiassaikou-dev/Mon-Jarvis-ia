import os


class SystemChecker:
    def verifier(self):
        elements = [
            "config/settings.json",
            "memory/memory.json",
            "agents",
            "skills",
            "brain"
        ]

        erreurs = []

        for element in elements:
            if not os.path.exists(element):
                erreurs.append(element)

        if erreurs:
            print("Éléments manquants :")
            for erreur in erreurs:
                print("-", erreur)
            return False

        print("Vérification du système réussie.")
        return True
