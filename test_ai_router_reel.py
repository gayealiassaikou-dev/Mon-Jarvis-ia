from core.ai_router import AIRouter
from core.ai_engine import AIEngine

engine = AIEngine()
router = AIRouter(engine)

reponse = router.demander(
    "Bonjour, réponds simplement : Jarvis fonctionne"
)

print(reponse)
