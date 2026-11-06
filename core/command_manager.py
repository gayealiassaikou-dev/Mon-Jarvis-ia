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
            return "Bonjour, je suis Sam Sarr. Systeme operationnel."

        elif commande in ["qui es tu", "qui es-tu", "présente toi"]:
            return "Je suis Sam Sarr, ton assistant IA personnel."

        elif commande == "agents":
            return "12 agents disponibles : Directeur IA, Développeur, Designer, Recherche, Business, Architecte IA, Mémoire, Automatisation, Testeur, Sécurité, Assistant vocal, Gestionnaire d'outils."

        elif commande == "memoire":
            return "La memoire de Sam Sarr est active."

        elif commande == "version":
            return "Sam Sarr version 0.1."

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
            return "Commandes disponibles : bonjour, qui es-tu, agents, memoire, version, heure, date, aide. Je sais aussi calculer (ex : combien font 12 fois 7)."

        elif re.match(r"^(?:joue(?: moi)?(?: la musique| la chanson| le morceau)?|(?:mets|lance)(?: moi)? (?:la musique|la chanson|le morceau)) (.+)$", commande):
            titre = re.match(r"^(?:joue(?: moi)?(?: la musique| la chanson| le morceau)?|(?:mets|lance)(?: moi)? (?:la musique|la chanson|le morceau)) (.+)$", commande).group(1)
            return self._jouer_musique(titre)

        else:
            return "Commande inconnue. Tape aide pour voir les commandes."

    def _jouer_musique(self, titre):
        import os, subprocess
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(racine, "jouer_musique.sh")
        if not os.path.exists(script) or not os.path.exists("/data/data/com.termux"):
            return "La lecture de musique marche seulement sur le telephone (Termux)."
        try:
            r = subprocess.run(["bash", script, titre], capture_output=True, text=True, timeout=40)
        except Exception as e:
            return "Impossible de lancer la musique : " + str(e)
        if r.returncode != 0:
            return "Je n'ai pas trouve cette musique."
        return "Je lance : " + titre + "."
