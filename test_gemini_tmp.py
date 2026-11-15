import os
from dotenv import load_dotenv
load_dotenv()
from core.ai_engine import AIEngine
from core.memory_manager import MemoryManager
from core.logger import Logger

e = AIEngine(memory_manager=MemoryManager(), logger=Logger())
e.outils_autorises = ["ecrire_fichier", "executer_programme_python"]
e.mode_action = True
print("mode_action:", e.mode_action)
print("--- Appel gemini ---")
try:
    r = e._demander_gemini("Ecris un fichier espace_travail/gemini_test.py qui affiche 'hello'")
    print("Reponse:", str(r)[:300])
    print("Outils executes:", len(e.derniers_resultats_outils))
    for res in e.derniers_resultats_outils:
        print("  -", res.get("outil"), res.get("statut"))
except Exception as ex:
    print("ERREUR:", type(ex).__name__, str(ex)[:200])
