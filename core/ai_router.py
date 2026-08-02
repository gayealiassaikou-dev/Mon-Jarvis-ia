import time


class AIRouter:
    """
    Routeur multi-IA pour Jarvis.
    Essaie les fournisseurs dans l'ordre défini.
    """

    def __init__(self, ai_engine):
        self.ai_engine = ai_engine
        self.fournisseurs = [
            "groq",
            "gemini",
            "openrouter",
            "mistral"
        ]

        self.indisponibles = {}

    def disponible(self, fournisseur):
        if fournisseur in self.indisponibles:
            if time.time() < self.indisponibles[fournisseur]:
                return False
            else:
                del self.indisponibles[fournisseur]

        return True

    def bloquer_temporairement(self, fournisseur, secondes=300):
        self.indisponibles[fournisseur] = time.time() + secondes

    def demander(self, message, contexte="", historique=None):

        erreurs = []

        for fournisseur in self.fournisseurs:

            if not self.disponible(fournisseur):
                continue

            try:
                print(f"[AI Router] Tentative : {fournisseur}")

                if fournisseur == "groq":
                    return self.ai_engine._demander_groq(
                        message, contexte, historique
                    )

                elif fournisseur == "gemini":
                    return self.ai_engine._demander_gemini(
                        message, contexte, historique
                    )

                else:
                    raise Exception(
                        f"{fournisseur} pas encore connecté"
                    )

            except Exception as e:
                erreurs.append(
                    f"{fournisseur}: {str(e)}"
                )

                if "429" in str(e) or "quota" in str(e).lower():
                    self.bloquer_temporairement(
                        fournisseur
                    )

                continue

        return (
            "Toutes les IA sont indisponibles :\n"
            + "\n".join(erreurs)
        )
