from core.paths import PROJECT_ROOT
import os


class SystemChecker:
    def verifier(self):
        elements = [
            str(PROJECT_ROOT / "config" / "settings.json"),
            str(PROJECT_ROOT / "memory" / "memory.json"),
            str(PROJECT_ROOT / "agents"),
            str(PROJECT_ROOT / "skills"),
            str(PROJECT_ROOT / "brain")
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
