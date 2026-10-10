import os


class AgentManager:
    def __init__(self):
        self.agents = {}
        self.charger_agents()

    def charger_agents(self):
        dossier = "agents"

        for fichier in os.listdir(dossier):
            if fichier.endswith(".md"):
                nom = fichier.replace(".md", "")
                chemin = os.path.join(dossier, fichier)

                with open(chemin, "r", encoding="utf-8") as f:
                    self.agents[nom] = f.read()

    def afficher_agents(self):
        print("Agents disponibles :")

        for agent in self.agents:
            print("-", agent)
