import os

def charger_contexte():
    fichiers = [
        "partenaire/brain/identity.md",
        "partenaire/brain/mission.md",
        "partenaire/brain/personality.md",
        "partenaire/brain/rules.md"
    ]

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    contenu_total = ""

    for fichier in fichiers:
        chemin = os.path.join(base, fichier)
        if os.path.exists(chemin):
            with open(chemin, "r", encoding="utf-8") as f:
                contenu_total += f.read() + "\n\n"

    regle = chr(10) + chr(10) + "REGLE IMPORTANTE : Utilise un outil seulement si la demande est explicite. Ne fais jamais une action non demandee, meme si elle semble utile. En cas de doute, demande confirmation avant agir."
    contenu_total += regle
    return contenu_total
