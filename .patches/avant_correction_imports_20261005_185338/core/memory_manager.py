import json
import os


class MemoryManager:
    def __init__(self):
        self.chemin = os.path.join("memory", "memory.json")
        self.memoire = self.charger()
        self._assurer_categories()

    def charger(self):
        with open(self.chemin, "r", encoding="utf-8") as fichier:
            return json.load(fichier)

    def sauvegarder(self):
        with open(self.chemin, "w", encoding="utf-8") as fichier:
            json.dump(self.memoire, fichier, indent=4, ensure_ascii=False)

    def _assurer_categories(self):
        categories = ["souvenirs", "notes", "historique", "projets", "decisions", "preferences", "connaissances", "erreurs"]
        modifie = False
        for cat in categories:
            if cat not in self.memoire:
                self.memoire[cat] = []
                modifie = True
        if modifie:
            self.sauvegarder()

    def ajouter_souvenir(self, souvenir):
        self.memoire["souvenirs"].append(souvenir)
        self.sauvegarder()

    def ajouter_echange(self, question, reponse):
        self.memoire["historique"].append({
            "question": question,
            "reponse": reponse
        })
        self.sauvegarder()

    def obtenir_historique_recent(self, nombre=5):
        return self.memoire["historique"][-nombre:]

    def memoriser(self, categorie, contenu):
        categories_valides = ["projets", "decisions", "preferences", "connaissances", "erreurs"]
        if categorie not in categories_valides:
            return f"Erreur : categorie invalide. Categories possibles : {', '.join(categories_valides)}"

        if contenu in self.memoire[categorie]:
            return f"Information deja presente dans {categorie}, pas de doublon ajoute."

        self.memoire[categorie].append(contenu)
        self.sauvegarder()
        return f"Information memorisee dans la categorie '{categorie}'."

    def rechercher_souvenir(self, mot_cle):
        mot_cle_min = mot_cle.lower()
        resultats = []

        categories = ["projets", "decisions", "preferences", "connaissances", "erreurs"]
        for cat in categories:
            for item in self.memoire.get(cat, []):
                if mot_cle_min in str(item).lower():
                    resultats.append(f"[{cat}] {item}")

        if not resultats:
            return "Aucune information trouvee pour ce mot-cle."

        return "\n".join(resultats)
