class TaskManager:
    def __init__(self):
        self.taches = []

    def ajouter_tache(self, tache):
        self.taches.append({
            "nom": tache,
            "statut": "en attente"
        })

    def afficher_taches(self):
        print("Liste des tâches :")

        for tache in self.taches:
            print("-", tache["nom"], "|", tache["statut"])
