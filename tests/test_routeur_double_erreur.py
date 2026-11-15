from core.ai_router import AIRouter


class TestAI:

    def _demander_groq(self, message, contexte="", historique=None):
        raise Exception("Erreur Groq quota")

    def _demander_gemini(self, message, contexte="", historique=None):
        raise Exception("Erreur Gemini quota")


router = AIRouter(TestAI())

print(router.demander("Test double panne IA"))
