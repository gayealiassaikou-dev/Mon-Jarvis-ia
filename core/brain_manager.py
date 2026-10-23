import os


class BrainManager:
    def __init__(self):
        self.connaissances = {}
        self.charger_brain()

    def charger_brain(self):
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        for sous_dossier in ("brain", "agents", "partenaire/brain"):
            dossier = os.path.join(racine, sous_dossier)
            if not os.path.isdir(dossier):
                continue

            for fichier in sorted(os.listdir(dossier)):
                if not fichier.endswith(".md"):
                    continue

                nom = f"{sous_dossier}/{fichier[:-3]}"
                chemin = os.path.join(dossier, fichier)

                try:
                    with open(chemin, "r", encoding="utf-8") as f:
                        self.connaissances[nom] = f.read()
                except (OSError, UnicodeError):
                    continue

    def afficher_brain(self):
        print("Connaissances du cerveau :")

        for connaissance in self.connaissances:
            print("-", connaissance)

    def rechercher_connaissances(self, requete, limite=3):
        """Retourne les connaissances les plus pertinentes pour une demande."""
        import re
        import unicodedata

        def normaliser(texte):
            texte = unicodedata.normalize("NFKD", str(texte).lower())
            texte = "".join(c for c in texte if not unicodedata.combining(c))
            return re.findall(r"[a-z0-9_]+", texte)

        if not isinstance(requete, str) or not requete.strip():
            return []

        try:
            limite = max(1, int(limite))
        except (TypeError, ValueError):
            limite = 3

        mots = set(normaliser(requete))
        mots_utiles = mots - {
            "a", "au", "aux", "avec", "ce", "ces", "dans", "de",
            "des", "du", "elle", "en", "et", "il", "je", "la",
            "le", "les", "ma", "mais", "me", "mon", "ne", "nos",
            "notre", "on", "ou", "par", "pas", "pour", "que",
            "qui", "sa", "se", "ses", "son", "sur", "ta", "te",
            "tes", "un", "une", "vos", "votre", "vous"
        }
        if not mots_utiles:
            mots_utiles = mots

        resultats = []
        for nom, contenu in self.connaissances.items():
            mots_titre = set(normaliser(nom.replace("_", " ")))
            mots_contenu = set(normaliser(contenu))
            score = (
                3 * len(mots_utiles & mots_titre)
                + len(mots_utiles & mots_contenu)
            )
            if score:
                resultats.append({
                    "nom": nom,
                    "contenu": contenu,
                    "score": score,
                })

        resultats.sort(key=lambda element: element["score"], reverse=True)
        return resultats[:limite]
