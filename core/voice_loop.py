"""Boucle vocale de Jarvis - extrait de jarvis.py."""


class VoiceLoopMixin:
    """Mixin fournissant la boucle d'ecoute vocale."""

    def mode_vocal(self, mots_retour_texte):
        print()
        print("=" * 50)
        print("🎙️ MODE VOCAL ACTIVÉ")
        print("Dites « reviens en texte » pour quitter.")
        print("=" * 50)

        derniere_reponse = None
        self._erreurs_vocales = 0

        self.voice_manager.parler(
            "Mode vocal activé. Parle après ce message, je t'écoute."
        )

        while True:
            try:
                print()
                print("[🎙️ Écoute directe — parlez...]" )

                commande_vocale = self.voice_manager.ecouter_et_transcrire(5)

                if not commande_vocale:
                    print("[Aucune parole détectée.]")
                    continue

                if commande_vocale.startswith("Erreur"):
                    if "aucune parole" in commande_vocale.lower():
                        print("[Silence, je continue d'écouter.]")
                        continue
                    print(f"[Erreur vocale] {commande_vocale}")
                    self._erreurs_vocales += 1
                    if self._erreurs_vocales >= 3:
                        print("[Trop d'erreurs, retour au mode texte.]")
                        self.voice_manager.parler("Trop d'erreurs. Je repasse en mode texte.")
                        break
                    continue

                print(f"👤 Vous : {commande_vocale}")
                self._erreurs_vocales = 0

                commande_lower = commande_vocale.lower().strip()

                # ---------------------------------------------------------
                # MODE ÉCOUTE DIRECTE
                # Le mot d'activation "Jarvis" est désactivé.
                # Toute phrase transcrite est traitée directement.
                # ---------------------------------------------------------
                print(f"[🎤 Commande vocale directe : {commande_vocale}]")

                # ---------------------------------------------------------
                # COMMANDES LOCALES : DATE ET HEURE
                # Ces commandes ne doivent pas passer par l'IA.
                # Le command_manager possède déjà la logique locale.
                # ---------------------------------------------------------
                reponse_locale = self.command_manager.traiter(commande_vocale)

                if reponse_locale.startswith(("Il est ", "Nous sommes ")):
                    print("[⚡ Commande locale date/heure.]")
                    derniere_reponse = reponse_locale
                    print("[🔊 Sam Sarr parle...]")
                    self.voice_manager.parler(reponse_locale)
                    continue


                if any(mot in commande_lower for mot in mots_retour_texte):
                    print()
                    print("[📝 Retour au mode texte.]")
                    self.voice_manager.parler(
                        "D'accord. Je repasse en mode texte."
                    )
                    break

                if commande_lower in ["quitter", "exit", "arrête jarvis", "arrête toi"]:
                    self.voice_manager.parler("D'accord. J'arrête Sam Sarr.")
                    self.logger.enregistrer("Arrêt de Jarvis par commande vocale")
                    print("Sam Sarr arrêté.")
                    return

                if commande_lower in [
                    "plus lentement",
                    "parle plus lentement",
                    "ralentis",
                    "ralentis ta voix"
                ]:
                    self.voice_manager.definir_vitesse(0.8)
                    self.voice_manager.parler(
                        "D'accord, je parle plus lentement."
                    )
                    continue

                if commande_lower in [
                    "plus rapidement",
                    "parle plus rapidement",
                    "accélère",
                    "accelere",
                    "accélère ta voix",
                    "accelere ta voix"
                ]:
                    self.voice_manager.definir_vitesse(1.2)
                    self.voice_manager.parler(
                        "D'accord, je parle plus rapidement."
                    )
                    continue

                if commande_lower in [
                    "vitesse normale",
                    "reviens à la vitesse normale",
                    "reviens a la vitesse normale",
                    "revient à la vitesse normale",
                    "revient a la vitesse normale"
                ]:
                    self.voice_manager.definir_vitesse(1.0)
                    self.voice_manager.parler(
                        "D'accord, je reviens à une vitesse normale."
                    )
                    continue

                if commande_lower in ["répète", "repete", "répète ça", "repete ça"]:
                    if derniere_reponse:
                        print("[🔁 Répétition de la dernière réponse.]")
                        self.voice_manager.parler(derniere_reponse)
                    else:
                        self.voice_manager.parler(
                            "Je n'ai pas encore de réponse à répéter."
                        )
                    continue

                print("[🧠 Sam Sarr réfléchit...]")

                reponse = self.traiter_commande(
                    commande_vocale,
                    retourner_reponse=True
                )

                if reponse:
                    derniere_reponse = reponse
                    print("[🔊 Sam Sarr parle...]")
                    self.voice_manager.parler(reponse)

            except KeyboardInterrupt:
                print()
                print("[Retour au mode texte.]")
                break
            except Exception as e:
                print(f"[Erreur mode vocal] {e}")
                self.voice_manager.parler(
                    "Une erreur est survenue. Je continue à t'écouter."
                )

