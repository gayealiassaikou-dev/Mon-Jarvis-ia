class ProjectManager:
    def __init__(self):
        self.projets = []

    def creer_projet(self, nom):
        projet = {
            "nom": nom,
            "statut": "en cours"
        }

        self.projets.append(projet)

    def afficher_projets(self):
        print("Projets actifs :")

        for projet in self.projets:
            print("-", projet["nom"], "|", projet["statut"])
