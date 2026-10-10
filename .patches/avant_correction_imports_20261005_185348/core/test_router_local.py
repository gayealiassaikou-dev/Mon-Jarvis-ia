from ai_engine import AIEngine
from ai_router import AIRouter

engine = AIEngine()
router = AIRouter(engine)

print(router.demander("Réponds simplement : Jarvis fonctionne"))
