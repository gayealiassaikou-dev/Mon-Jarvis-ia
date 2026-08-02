import sys
sys.path.append("core")

from ai_engine import AIEngine

print("Test routeur démarré")

ia = AIEngine()

reponse = ia.router.demander(
    "Analyse le projet Voice Music en quelques lignes",
    contexte="Tu es un assistant de test."
)

print(reponse)
