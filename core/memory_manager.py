import json
import os
import re
import unicodedata


class MemoryManager:
    def __init__(self):
        dossier_memoire = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memory"))
        self.chemin = os.path.join(dossier_memoire, "memory.json")
        self.chemin_archive = os.path.join(dossier_memoire, "historique_archive.json")
        self.limite_historique = 200
        self.memoire = self.charger()
        self._assurer_categories()

    def charger(self):
        try:
            with open(self.chemin, "r", encoding="utf-8") as fichier:
                return json.load(fichier)
        except FileNotFoundError:
            return {}

    def _ecrire_json_atomique(self, chemin, donnees):
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        temporaire = chemin + ".tmp"
        with open(temporaire, "w", encoding="utf-8") as fichier:
            json.dump(donnees, fichier, indent=4, ensure_ascii=False)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(temporaire, chemin)

    def sauvegarder(self):
        self._ecrire_json_atomique(self.chemin, self.memoire)

    def _archiver_anciens_echanges(self):
        historique = self.memoire["historique"]
        if len(historique) <= self.limite_historique:
            return

        anciens = historique[:-self.limite_historique]
        recents = historique[-self.limite_historique:]
        archive_existante = os.path.exists(self.chemin_archive)

        try:
            if archive_existante:
                with open(self.chemin_archive, "r", encoding="utf-8") as fichier:
                    archive = json.load(fichier)
                if not isinstance(archive, list) or not all(
                    isinstance(echange, dict) for echange in archive
                ):
                    return
            else:
                archive = []

            archive_precedente = list(archive)
            self._ecrire_json_atomique(
                self.chemin_archive, archive + anciens
            )

            historique_precedent = historique
            self.memoire["historique"] = recents
            try:
                self.sauvegarder()
            except Exception:
                self.memoire["historique"] = historique_precedent
                try:
                    self._ecrire_json_atomique(
                        self.chemin_archive, archive_precedente
                    )
                except Exception:
                    pass
                raise
        except Exception:
            return

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
        if len(self.memoire["historique"]) > self.limite_historique:
            self._archiver_anciens_echanges()
            if len(self.memoire["historique"]) > self.limite_historique:
                self.sauvegarder()
        else:
            self.sauvegarder()

    def obtenir_historique_recent(self, nombre=5):
        return self.memoire["historique"][-nombre:]

    def memoriser(self, categorie, contenu):
        categories_valides = ["projets", "decisions", "preferences", "connaissances", "erreurs"]
        if categorie not in categories_valides:
            return f"Erreur : categorie invalide. Categories possibles : {', '.join(categories_valides)}"

        def _norm(texte):
            texte = unicodedata.normalize("NFD", str(texte).casefold().replace("’", "'"))
            return "".join(c for c in texte if unicodedata.category(c) != "Mn").strip()

        contenu_norm = _norm(contenu)
        if len(contenu_norm) < 3 or re.match(
            r"(je peux (aider|fournir|apprendre|detecter|vous)|mon role est|"
            r"je suis partenaire|sous-titrage|l'utilisateur demande a plusieurs reprises)",
            contenu_norm,
        ):
            return "Information ignoree : ce n'est pas un fait utile sur l'utilisateur."
        for existant in self.memoire[categorie]:
            if _norm(existant) == contenu_norm:
                return f"Information deja presente dans {categorie}, pas de doublon ajoute."

        if contenu in self.memoire[categorie]:
            return f"Information deja presente dans {categorie}, pas de doublon ajoute."

        self.memoire[categorie].append(contenu)
        self.sauvegarder()
        return f"Information memorisee dans la categorie '{categorie}'."

    def rechercher_souvenir(self, mot_cle):
        def normaliser(texte):
            texte = unicodedata.normalize("NFD", str(texte).casefold())
            return "".join(
                caractere for caractere in texte
                if unicodedata.category(caractere) != "Mn"
            )

        mot_cle_normalise = normaliser(mot_cle).strip()
        if not mot_cle_normalise:
            return "Aucune information trouvee pour ce mot-cle."

        resultats = []
        categories = [
            "projets", "decisions", "preferences",
            "connaissances", "erreurs"
        ]

        for categorie in categories:
            for item in self.memoire.get(categorie, []):
                if mot_cle_normalise in normaliser(item):
                    resultat = f"[{categorie}] {item}"
                    if resultat not in resultats:
                        resultats.append(resultat)

        if not resultats:
            return "Aucune information trouvee pour ce mot-cle."

        return "\n".join(resultats)

    def rechercher_souvenirs_pertinents(self, question, limite=5):
        """Retrouve les souvenirs les plus pertinents pour une question."""
        def normaliser(texte):
            texte = unicodedata.normalize("NFD", str(texte).casefold())
            return "".join(
                caractere for caractere in texte
                if unicodedata.category(caractere) != "Mn"
            )

        def racine(mot):
            # Pluriel simple : "projets" -> "projet".
            if len(mot) > 3 and mot.endswith(("s", "x")):
                return mot[:-1]
            return mot

        mots_vides = {
            "alors", "avec", "comment", "dans", "des", "est", "faire",
            "fait", "pour", "peux", "peut", "quelle", "quelles", "quel",
            "quels", "qui", "quoi", "sont", "sur", "tout", "tous",
            "une", "uniquement", "mon", "ma", "mes", "ton", "ta", "tes",
            "son", "sa", "ses", "les", "leur", "leurs", "cela", "ceci",
            "mais", "donc", "par", "pas", "plus", "que", "aux",
            "du", "de", "la", "le", "un", "et", "ou", "en",
            "je", "tu", "il", "elle", "nous", "vous", "ils", "elles"
        }

        mots_question = {
            racine(mot) for mot in re.findall(r"\w+", normaliser(question))
            if len(mot) >= 3 and mot not in mots_vides
        }
        if not mots_question or limite <= 0:
            return []

        categories = (
            "projets", "decisions", "preferences",
            "connaissances", "erreurs", "souvenirs", "notes"
        )
        resultats = []

        for categorie in categories:
            # Si la question nomme la categorie ("mes preferences"),
            # ses elements sont retournes meme sans mot en commun.
            categorie_visee = racine(categorie) in mots_question
            for item in self.memoire.get(categorie, []):
                texte = normaliser(item)
                mots_item = {racine(mot) for mot in re.findall(r"\w+", texte)}
                correspondances = mots_question & mots_item
                if not correspondances and not categorie_visee:
                    continue

                score = len(correspondances)
                if any(mot in texte for mot in mots_question if len(mot) >= 5):
                    score += 1
                if categorie_visee:
                    score += 1

                resultats.append({
                    "score": score,
                    "texte": f"[{categorie}] {item}"
                })

        resultats.sort(key=lambda resultat: resultat["score"], reverse=True)
        return [resultat["texte"] for resultat in resultats[:limite]]
