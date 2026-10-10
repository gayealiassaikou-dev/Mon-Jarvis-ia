import os


class SkillManager:
    def __init__(self):
        self.skills = {}
        self.charger_skills()

    def charger_skills(self):
        dossier = "skills"

        for fichier in os.listdir(dossier):
            if fichier.endswith(".md"):
                nom = fichier.replace(".md", "")
                chemin = os.path.join(dossier, fichier)

                with open(chemin, "r", encoding="utf-8") as f:
                    self.skills[nom] = f.read()

    def afficher_skills(self):
        print("Compétences disponibles :")

        for skill in self.skills:
            print("-", skill)
