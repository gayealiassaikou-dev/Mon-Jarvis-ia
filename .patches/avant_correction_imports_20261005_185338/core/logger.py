from datetime import datetime


class Logger:
    def __init__(self):
        self.fichier = "jarvis.log"

    def enregistrer(self, message):
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.fichier, "a", encoding="utf-8") as f:
            f.write(f"[{date}] {message}\n")
