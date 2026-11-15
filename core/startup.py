"""Boucle de demarrage et boucle principale de Jarvis."""


class StartupMixin:
    """Mixin fournissant start() - la boucle REPL principale."""

    def start(self):
        if not self.system_checker.verifier():
            print("Erreur : système incomplet.")
            return

        self.logger.enregistrer("Démarrage de Jarvis")

        print(f"{self.nom} version {self.version} démarré.")
        print("Mémoire chargée.")
        self.agent_manager.afficher_agents()
        self.skill_manager.afficher_skills()
        self.brain_manager.afficher_brain()
        self.task_manager.afficher_taches()
        self.project_manager.afficher_projets()
        self.knowledge_manager.afficher_connaissances()
        self.mission_manager.purger()
        _nettoyees = self.mission_manager.nettoyer_sous_taches_orphelines()
        if _nettoyees:
            print(f"[Reprise] {_nettoyees} sous-tache(s) orpheline(s) remise(s) en attente")
        self.mission_manager.afficher_missions()
        missions_reprise = self.mission_manager.missions_a_reprendre()
        if missions_reprise:
            print(f"\n{len(missions_reprise)} mission(s) a reprendre :")
            for m in missions_reprise:
                print(f"  - [{m['id']}] {m['nom']} ({m['statut']}, {m['priorite']})")
        else:
            print("\nAucune mission a reprendre.")
        print("Système prêt.")

        mots_declencheurs_vocal = [
            "parle moi",
            "parle-moi",
            "je veux parler",
            "vocal",
            "voix",
            "parler"
        ]

        mots_retour_texte = [
            "reviens en texte",
            "stop vocal",
            "mode texte",
            "retour texte",
            "retourne en texte",
            "mode écriture",
            "mode ecriture",
            "passe en texte",
            "repasse en texte"
        ]

        derniere_reponse_texte = None

        while True:
            try:
                commande = input("Vous : ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                self.logger.enregistrer("Arrêt de Jarvis")
                print("Sam Sarr arrêté.")
                break

            if not commande:
                continue

            commande_lower = commande.lower()

            if commande_lower in ["quitter", "exit", "stop"]:
                self.logger.enregistrer("Arrêt de Jarvis")
                print("Sam Sarr arrêté.")
                break

            commandes_lecture = (
                "lis tout le résultat à haute voix",
                "lis tout le resultat a haute voix",
                "lis la dernière réponse",
                "lis la derniere reponse",
                "lis ta réponse à haute voix",
                "lis ta reponse a haute voix",
                "lis le résultat à haute voix",
                "lis le resultat a haute voix",
                "lis à haute voix",
                "lis a haute voix",
                "réponds-moi à haute voix",
                "reponds-moi a haute voix",
                "réponds moi à haute voix",
                "reponds moi a haute voix",
                "répond moi à haute voix",
                "repond moi a haute voix",
                "réponds à haute voix",
                "reponds a haute voix",
            )

            phrase_lecture = next(
                (p for p in commandes_lecture if p in commande_lower),
                None
            )

            import re as _re
            motif_lecture = None
            if not phrase_lecture:
                motif_lecture = _re.search(
                    r"\b(?:(?:lis|lire|lit|réponds|reponds|répond|repond|dis)(?:[- ]moi)?(?:[- ](?:le|la))?\s*(?:le\s+r[ée]sultat|la\s+r[ée]ponse|ta\s+r[ée]ponse|tout)?\s*)?(?:[àa]\s+)?(?:haute voix|voix haute)\b",
                    commande_lower
                )

            if phrase_lecture or motif_lecture:
                if phrase_lecture:
                    debut_phrase = commande_lower.index(phrase_lecture)
                    fin_phrase = debut_phrase + len(phrase_lecture)
                else:
                    debut_phrase = motif_lecture.start()
                    fin_phrase = motif_lecture.end()
                question = (
                    commande[:debut_phrase] + commande[fin_phrase:]
                ).strip(" ,.!?;:-")
                question = _re.sub(r"\s+et$", "", question, flags=_re.IGNORECASE).strip(" ,.!?;:-")

                if question:
                    reponse = self.traiter_commande(
                        question,
                        retourner_reponse=True
                    )
                    if isinstance(reponse, str) and reponse.strip():
                        derniere_reponse_texte = reponse
                        print("[Lecture de la réponse à haute voix...]")
                        self.voice_manager.parler(reponse)
                elif derniere_reponse_texte:
                    print("[Lecture de la dernière réponse...]")
                    self.voice_manager.parler(derniere_reponse_texte)
                else:
                    print("Aucune réponse précédente à lire.")
                continue

            if any(mot in commande_lower for mot in mots_declencheurs_vocal):
                self.mode_vocal(mots_retour_texte)
                continue

            reponse_texte = self.traiter_commande(
                commande,
                retourner_reponse=True
            )
            if isinstance(reponse_texte, str) and reponse_texte.strip():
                derniere_reponse_texte = reponse_texte

