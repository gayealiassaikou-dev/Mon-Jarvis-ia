import re
import time


def masquer_secrets(texte):
    """Remplace les cles API visibles dans un message d'erreur."""
    texte = str(texte)
    texte = re.sub(
        r"(?i)([?&](?:key|api_key|apikey|token|access_token)=)"
        r"[^&\s'\"]+",
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

    def __init__(self, ai_engine):
        self.ai_engine = ai_engine
        ordre_defaut = ("mistral", "openrouter", "groq", "gemini")
        configuration = getattr(ai_engine, "providers", {})
        self.fournisseurs = sorted(
            ordre_defaut,
            key=lambda nom: (
                configuration.get(nom, {}).get(
                    "priorite", ordre_defaut.index(nom) + 1
                ),
                ordre_defaut.index(nom),
            ),
        )

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

                if "429" in str(e) or "quota" in str(e).lower():
                    self.bloquer_temporairement(
                        fournisseur
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

        return (
            "Toutes les IA sont indisponibles :\n"
            + "\n".join(erreurs)
        )
