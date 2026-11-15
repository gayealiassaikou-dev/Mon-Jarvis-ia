"""Decision locale sans LLM - extraite de decision_engine.py."""


class DecisionLocalMixin:
    """Mixin fournissant _decision_locale()."""

    def _decision_locale(self, demande, liste_agents):
        """Choix d'agent sans IA pour les demandes simples (None = laisser l'IA décider)."""
        import re
        import unicodedata
        if not isinstance(demande, str) or not demande.strip() or len(demande) > 400:
            return None
        texte = unicodedata.normalize("NFKD", demande.casefold())
        texte = "".join(c for c in texte if not unicodedata.combining(c))
        mots = re.findall(r"\w+", texte)

        # Routage local prioritaire des commandes de contrôle Android.
        agent_telephone = "10_assistant_vocal_ia"
        outil_telephone = None
        mots_action = {
            "regle", "regler", "mets", "met", "augmente", "augmenter",
            "baisse", "baisser", "diminue", "diminuer", "monte",
            "allume", "eteins", "active", "desactive", "change", "fixe",
        }
        mots_lecture = {
            "lis", "lire", "lecture", "consulte", "affiche",
            "montre", "voir", "verifie", "donne",
        }

        if "notification" in mots or "notifications" in mots:
            if mots_lecture.intersection(mots):
                outil_telephone = "lire_notifications"
            elif {"envoie", "envoyer", "envoi", "notifie", "notifier"}.intersection(mots):
                outil_telephone = "envoyer_notification"
        elif "batterie" in mots:
            outil_telephone = "lire_batterie"
        elif "luminosite" in mots and mots_action.intersection(mots):
            outil_telephone = "regler_luminosite"
        elif "volume" in mots and mots_action.intersection(mots):
            outil_telephone = "regler_volume"
        elif {"lampe", "torche", "flash"}.intersection(mots) and mots_action.intersection(mots):
            outil_telephone = "lampe_torche"
        elif {"wifi", "wi"}.intersection(mots) and ("wifi" in mots or "fi" in mots):
            outil_telephone = "lire_wifi"
        elif ("papiers" in mots and "presse" in mots) or "clipboard" in mots:
            if mots_lecture.intersection(mots):
                outil_telephone = "lire_presse_papiers"

        if (
            outil_telephone
            and agent_telephone in liste_agents
            and outil_telephone in self.outils_disponibles
        ):
            outils_autorises = filtrer_outils(
                agent_telephone, [outil_telephone]
            )
            if outil_telephone in outils_autorises:
                return {
                    "agent": agent_telephone,
                    "complexite": "simple",
                    "analyse": {
                        "difficulte": "faible",
                        "risques": "faible",
                        "validation_requise": False,
                        "resume": demande,
                    },
                    "outils_suggeres": outils_autorises,
                }

        racines_action = (
            "supprim", "efface", "cre", "ecri", "modifi", "install", "deploi",
            "lance", "execut", "lis", "ouvr", "ajout", "renomm", "deplac",
            "push", "commit", "memoris", "retien", "mission", "tache",
            "projet", "cherch", "recherch", "github", "git", "depot",
            "repo", "fichier", "dossier",
        )
        if any(m.startswith(r) for m in mots for r in racines_action):
            return None
        themes = {
            "01_developpeur": {"code", "python", "bug", "programme", "script",
                               "flask", "termux", "fonction", "variable", "api",
                               "syntaxe", "compilation"},
            "02_designer": {"design", "couleur", "couleurs", "logo", "maquette",
                            "interface", "police", "style"},
            "04_business": {"business", "client", "clients", "vente", "ventes",
                            "marketing", "prix", "entreprise", "boutique",
                            "commerce", "commercant"},
            "05_architecte_ia": {"architecture"},
            "09_securite_ia": {"securite", "faille", "piratage", "chiffrement"},
        }
        scores = []
        for agent, vocabulaire in themes.items():
            if agent in liste_agents:
                scores.append((sum(1 for m in mots if m in vocabulaire), agent))
        scores.sort(reverse=True)
        if not scores or scores[0][0] < 1:
            return None
        if len(scores) > 1 and scores[1][0] == scores[0][0]:
            return None
        return {
            "agent": scores[0][1],
            "complexite": "simple",
            "analyse": {
                "difficulte": "moyenne",
                "risques": "faible",
                "validation_requise": False,
                "resume": demande,
            },
            "outils_suggeres": [],
        }

