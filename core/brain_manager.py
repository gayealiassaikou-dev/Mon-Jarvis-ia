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
        """Classe les documents selon leur pertinence pour une demande."""
        import re
        import unicodedata
        from collections import Counter

        def normaliser(texte):
            texte = unicodedata.normalize("NFKD", str(texte).casefold())
            texte = "".join(
                c for c in texte if not unicodedata.combining(c)
            )
            return re.findall(r"[a-z0-9_]+", texte)

        if not isinstance(requete, str) or not requete.strip():
            return []

        try:
            limite = max(1, int(limite))
        except (TypeError, ValueError):
            limite = 3

        mots_vides = {
            "a", "au", "aux", "avec", "ce", "ces", "dans", "de",
            "des", "du", "elle", "en", "et", "il", "je", "la",
            "le", "les", "ma", "mais", "me", "mon", "ne", "nos",
            "notre", "on", "ou", "par", "pas", "pour", "que",
            "qui", "sa", "se", "ses", "son", "sur", "ta", "te",
            "tes", "un", "une", "vos", "votre", "vous",
        }

        mots_requete = normaliser(requete)
        mots_utiles = set(mots_requete) - mots_vides
        if not mots_utiles:
            mots_utiles = set(mots_requete)
        if not mots_utiles:
            return []

        phrase = " ".join(mots_requete)
        resultats = []

        for nom, contenu in self.connaissances.items():
            contenu = str(contenu)
            titre = " ".join(normaliser(nom.replace("_", " ")))
            texte_normalise = " ".join(normaliser(contenu))
            compteur = Counter(normaliser(contenu))
            mots_titre = set(normaliser(titre))

            correspondances = mots_utiles & set(compteur)
            couverture = len(correspondances)

            score = (
                5 * len(mots_utiles & mots_titre)
                + sum(min(compteur[mot], 4) * 2 for mot in mots_utiles)
                + couverture * 3
            )

            if phrase and phrase in titre:
                score += 10
            if phrase and phrase in texte_normalise:
                score += 8

            if score:
                resultats.append({
                    "nom": nom,
                    "contenu": contenu,
                    "score": score,
                })

        resultats.sort(
            key=lambda element: (-element["score"], element["nom"])
        )
        return resultats[:limite]
