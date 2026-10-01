import re
from datetime import datetime

class CommandManager:

    def traiter(self, commande):
        commande = commande.lower().strip()
        commande = commande.replace("’", "'")
        commande = re.sub(r"\b((s|qu)'il (te|vous) pla[iî]t|svp|stp)\b", " ", commande)
        commande = re.sub(r"[?!.,;:]+", " ", commande)
        commande = re.sub(r"\s+", " ", commande).strip()

        if commande in ["bonjour", "salut", "hello"]:
            return "Bonjour, je suis Jarvis. Systeme operationnel."

        elif commande in ["qui es tu", "qui es-tu", "présente toi"]:
            return "Je suis Jarvis, ton assistant IA personnel."

        elif commande == "agents":
            return "Agents disponibles : Directeur IA, Developpeur, Designer, Recherche, Business."

        elif commande == "memoire":
            return "La memoire de Jarvis est active."

        elif commande == "version":
            return "Jarvis version 0.1."

        elif commande == "heure":
            return f"Il est {datetime.now().strftime('%H:%M')}."

        elif commande in [
            "quelle heure est-il",
            "quelle heure il est",
            "il est quelle heure",
            "il fait quelle heure",
            "il fait quel heure",
            "il fait quel heur",
            "il fait quelle heur",
            "quelle heure est il",
            "quelle heur est il",
            "quel heure est il",
            "quel heur est il",
            "donne moi l'heure",
            "donne-moi l'heure",
            "donne l'heure",
        ]:
            return f"Il est {datetime.now().strftime('%H:%M')}."

        elif commande == "date":
            return f"Nous sommes le {datetime.now().strftime('%d/%m/%Y')}."

        elif commande in [
            "quelle est la date",
            "quelle date sommes-nous",
            "quelle date sommes nous",
            "on est quel jour",
            "quel jour sommes-nous",
            "quel jour sommes nous",
        ]:
            return f"Nous sommes le {datetime.now().strftime('%d/%m/%Y')}."

        elif commande in [
            "il fait quelle heure et la date aujourd'hui",
            "il fait quelle heure et la date aujourd hui",
            "quelle heure et quelle date aujourd'hui",
            "quelle heure et quelle date aujourd hui",
            "donne moi l'heure et la date",
            "donne-moi l'heure et la date",
            "donne l'heure et la date",
        ]:
            maintenant = datetime.now()
            return (
                f"Il est {maintenant.strftime('%H:%M')} "
                f"et nous sommes le {maintenant.strftime('%d/%m/%Y')}."
            )

        elif commande == "aide":
            return "Commandes disponibles : bonjour, qui es-tu, agents, memoire, version, aide."

        else:
            return "Commande inconnue. Tape aide pour voir les commandes."
