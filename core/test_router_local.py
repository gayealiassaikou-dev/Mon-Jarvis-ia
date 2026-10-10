from core.ai_engine import AIEngine
from core.ai_router import AIRouter

engine = AIEngine()
router = AIRouter(engine)

print(router.demander("Réponds simplement : Jarvis fonctionne"))
