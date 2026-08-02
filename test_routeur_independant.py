from core.ai_router import AIRouter


class TestAI:
    def _demander_groq(self, message, contexte="", historique=None):
        raise Exception("Erreur 429 quota Groq")
    def _demander_gemini(self, message, contexte="", historique=None):
        return "Test Gemini OK"


ia_test = TestAI()

router = AIRouter(ia_test)

reponse = router.demander(
    "Teste le système IA",
    contexte="",
    historique=None
)

print(reponse)
