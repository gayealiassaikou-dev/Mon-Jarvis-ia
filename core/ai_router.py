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

    def demander(self, message, contexte="", historique=None):

        erreurs = []

        for fournisseur in self.fournisseurs:

            if not self.disponible(fournisseur):
                continue

            try:
                print(f"[AI Router] Tentative : {fournisseur}")

                if fournisseur == "groq":
                    reponse = self.ai_engine._demander_groq(
                        message, contexte, historique
                    )

                elif fournisseur == "gemini":
                    reponse = self.ai_engine._demander_gemini(
                        message, contexte, historique
                    )

                elif fournisseur == "openrouter":
                    reponse = self.ai_engine._demander_openrouter(
                        message, contexte, historique
                    )

                elif fournisseur == "mistral":
                    reponse = self.ai_engine._demander_mistral(
                        message, contexte, historique
                    )

                elif fournisseur == "nvidia":
                    reponse = self.ai_engine._demander_nvidia(
                        message, contexte, historique
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
                        return (
                            "Erreur IA après exécution d'une action avec "
                            f"{fournisseur}. Fallback automatique annulé "
                            "pour éviter une double exécution."
                        )

                    erreurs.append(
                        f"{fournisseur}: réponse d'échec « erreur ia »"
                    )
                    continue

                return reponse

            except Exception as e:
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
