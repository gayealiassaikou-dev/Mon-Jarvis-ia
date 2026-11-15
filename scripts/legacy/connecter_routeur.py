fichier = "core/ai_engine.py"

with open(fichier, "r", encoding="utf-8") as f:
    code = f.read()

if "from core.ai_router import AIRouter" not in code:
    code = code.replace(
        "from dotenv import load_dotenv",
        "from dotenv import load_dotenv\nfrom core.ai_router import AIRouter"
    )

if "self.router = AIRouter(self)" not in code:
    code = code.replace(
        "self.memory_manager = memory_manager",
        "self.memory_manager = memory_manager\n        self.router = AIRouter(self)"
    )

with open(fichier, "w", encoding="utf-8") as f:
    f.write(code)

print("Routeur connecté.")
