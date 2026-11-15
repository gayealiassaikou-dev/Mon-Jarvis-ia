import re
import time


def masquer_secrets(texte):
    """Masque les clés API, jetons et mots de passe dans les erreurs."""
    texte = str(texte)

    texte = re.sub(
        r"""(?i)(["']?(?:api[_-]?key|apikey|access[_-]?token|refresh[_-]?token|client[_-]?secret|key|token|secret|password)["']?\s*[:=]\s*["']?)([^"'\s&,}]+)""",
        r"\1***",
        texte,
    )

    texte = re.sub(
        r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}",
        r"\1***",
        texte,
    )

    return texte


class AIRouter:
    """
    Routeur multi-IA pour Jarvis.
    Essaie les fournisseurs dans l'ordre défini.
    """

    def __init__(self, ai_engine, persister_quotas=False):
        self.ai_engine = ai_engine
        self.persister_quotas = persister_quotas
        configuration = getattr(ai_engine, "providers", {})
        self.fournisseurs = sorted(
            configuration,
            key=lambda nom: (
                configuration.get(nom, {}).get("priorite", 999),
                nom,
            ),
        )

        self.indisponibles = {}
        # Trackers de latence et echecs consecutifs par provider
        self.latences = {}  # {nom: [sec, sec, ...]} - 10 dernieres
        self.echecs_consecutifs = {}  # {nom: count}
        self._persister("restaurer_blocages", self)

    def disponible(self, fournisseur):
        if fournisseur in self.indisponibles:
            if time.time() < self.indisponibles[fournisseur]:
                return False
            else:
                del self.indisponibles[fournisseur]

        return True

    def _persister(self, fonction, *args):
        if not self.persister_quotas:
            return
        try:
            import threading
            from core import quotas

            threading.Thread(
                target=getattr(quotas, fonction), args=args, daemon=True
            ).start()
        except Exception:
            pass

    def bloquer_temporairement(self, fournisseur, secondes=300, erreur=""):
        self.indisponibles[fournisseur] = time.time() + secondes
        self._persister("marquer_bloque", fournisseur, erreur, secondes)

    def _enregistrer_latence(self, fournisseur, secondes):
        """Garde les 10 dernieres latences par provider."""
        lst = self.latences.setdefault(fournisseur, [])
        lst.append(secondes)
        if len(lst) > 10:
            del lst[0]
        # Succes = reset echecs consecutifs
        self.echecs_consecutifs[fournisseur] = 0

    def _enregistrer_echec(self, fournisseur):
        """Incremente les echecs consecutifs."""
        self.echecs_consecutifs[fournisseur] = self.echecs_consecutifs.get(fournisseur, 0) + 1

    def _latence_moyenne(self, fournisseur):
        """Latence moyenne (None si jamais appele)."""
        lst = self.latences.get(fournisseur, [])
        if not lst:
            return None
        return sum(lst) / len(lst)

    def _fournisseurs_ordonnes(self):
        """Trie les providers par : echecs consecutifs, puis latence moyenne."""
        def cle(nom):
            echecs = self.echecs_consecutifs.get(nom, 0)
            lat = self._latence_moyenne(nom)
            # Echecs consecutifs = priorite haute (mauvaise)
            # Latence moyenne = plus c'est rapide mieux c'est
            # Jamais appele (lat=None) = neutre
            if lat is None:
                lat_rank = 999  # entre rapide (0-15) et lent (>15)
            else:
                lat_rank = lat
            return (echecs, lat_rank)
        return sorted(self.fournisseurs, key=cle)


    def demander(self, message, contexte="", historique=None, on_chunk=None):

        erreurs = []

        # Court-circuit : si 2 providers consecutifs ont echoue 3+ fois,
        # on les skip pour aller plus vite au provider sain
        ordre = self._fournisseurs_ordonnes()
        echecs_rapides = 0

        for fournisseur in ordre:

            if not self.disponible(fournisseur):
                continue

            # Skip si ce provider a 3+ echecs consecutifs ET on a deja 2 skips
            if self.echecs_consecutifs.get(fournisseur, 0) >= 3 and echecs_rapides < 2:
                echecs_rapides += 1
                erreurs.append(f"{fournisseur}: skip (3+ echecs consecutifs)")
                continue

            try:
                print(f"[AI Router] Tentative : {fournisseur}")
                _t_debut = time.time()

                if fournisseur == "groq":
                    reponse = self.ai_engine._demander_groq(
                        message, contexte, historique, on_chunk=on_chunk
                    )

                elif fournisseur == "gemini":
                    reponse = self.ai_engine._demander_gemini(
                        message, contexte, historique, on_chunk=on_chunk
                    )

                elif fournisseur == "openrouter":
                    reponse = self.ai_engine._demander_openrouter(
                        message, contexte, historique, on_chunk=on_chunk
                    )

                elif fournisseur == "mistral":
                    reponse = self.ai_engine._demander_mistral(
                        message, contexte, historique, on_chunk=on_chunk
                    )

                elif fournisseur == "nvidia":
                    reponse = self.ai_engine._demander_nvidia(
                        message, contexte, historique, on_chunk=on_chunk
                    )

                else:
                    raise Exception(
                        f"{fournisseur} pas encore connecté"
                    )

                if (
                    isinstance(reponse, str)
                    and reponse.strip().casefold() == "erreur ia"
                ):
                    if getattr(self.ai_engine, "action_engagee", False):
                        # Vérifier les résultats des outils
                        resultats = getattr(self.ai_engine, "derniers_resultats_outils", [])
                        if resultats and all(r.get("statut") == "succes" and r.get("execute") for r in resultats):
                            details = []
                            for r in resultats:
                                outil = r.get("outil", "inconnu")
                                resultat = str(r.get("resultat", ""))
                                if len(resultat) > 300:
                                    resultat = resultat[:300] + "..."
                                details.append(f"{outil} : {resultat}")
                            details_str = "; ".join(details)
                            return (
                                f"Erreur IA — Actions exécutées, mais la réponse finale a échoué chez {fournisseur} (ErreurIA). "
                                f"Résultats des outils : {details_str}"
                            )
                        return (
                            "Erreur IA après exécution d'une action avec "
                            f"{fournisseur}. Fallback automatique annulé "
                            "pour éviter une double exécution."
                        )

                    erreurs.append(
                        f"{fournisseur}: réponse d'échec « erreur ia »"
                    )
                    continue

                # Succes : enregistrer latence
                self._enregistrer_latence(fournisseur, time.time() - _t_debut)
                return reponse

            except Exception as e:
                # Echec : incrementer compteur
                self._enregistrer_echec(fournisseur)
                erreurs.append(
                    f"{fournisseur}: {masquer_secrets(str(e))}"
                )

                erreur = str(e).lower()
                if (
                    any(code in erreur for code in ("402", "429", "503"))
                    or "quota" in erreur
                ):
                    self.bloquer_temporairement(
                        fournisseur, erreur=masquer_secrets(str(e))
                    )

                # Si un outil a déjà été engagé, l'erreur peut être
                # survenue après une action réelle. Ne pas relancer
                # automatiquement la même demande avec un autre fournisseur.
                if getattr(self.ai_engine, "action_engagee", False):
                    # Vérifier les résultats des outils
                    resultats = getattr(self.ai_engine, "derniers_resultats_outils", [])
                    if resultats and all(r.get("statut") == "succes" and r.get("execute") for r in resultats):
                        details = []
                        for r in resultats:
                            outil = r.get("outil", "inconnu")
                            resultat = str(r.get("resultat", ""))
                            if len(resultat) > 300:
                                resultat = resultat[:300] + "..."
                            details.append(f"{outil} : {resultat}")
                        details_str = "; ".join(details)
                        return (
                            f"Erreur IA — Actions exécutées, mais la réponse finale a échoué chez {fournisseur} ({type(e).__name__}). "
                            f"Résultats des outils : {details_str}"
                        )
                    return (
                        "Erreur IA après exécution d'une action avec "
                        f"{fournisseur} : "
                        f"{type(e).__name__}: {masquer_secrets(str(e))}. "
                        "Fallback automatique annulé pour éviter "
                        "une double exécution."
                    )

                continue

        detail = (
            "\n".join(erreurs)
            if erreurs
            else "Fournisseurs temporairement bloqués (quota ou crédits), "
                 "nouvel essai dans quelques minutes."
        )
        return (
            "Toutes les IA sont indisponibles :\n"
            + detail
            + "\nEn attendant, je peux encore répondre sans IA : calculs, "
              "heure, date, espace libre, projets, tâches, mémoire."
        )
