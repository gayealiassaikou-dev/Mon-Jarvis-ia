import sys
sys.path.insert(0, "core")

from jarvis import Jarvis
from voice_manager import VoiceManager

def main():
    print("Demarrage du mode vocal Jarvis...")
    jarvis = Jarvis()
    voix = VoiceManager()

    voix.parler("Mode vocal active. Je vous ecoute.")
    print("Mode vocal actif. Dites 'stop' ou 'au revoir' pour quitter.")

    while True:
        print("\n[Parlez maintenant - 5 secondes]")
        texte = voix.ecouter_et_transcrire(duree_secondes=5)

        if not texte or texte.startswith("Erreur"):
            print(f"Probleme : {texte}")
            continue

        print(f"Vous avez dit : {texte}")

        if texte.strip().lower() in ["stop", "au revoir", "arrete", "quitte"]:
            voix.parler("A bientot.")
            print("Fin du mode vocal.")
            break

        reponse = jarvis.traiter_commande(texte, retourner_reponse=True)
        print(f"Jarvis : {reponse}")
        voix.parler(reponse)

if __name__ == "__main__":
    main()
