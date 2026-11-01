from core.jarvis import Jarvis


def main():
    jarvis = Jarvis()
    try:
        from core.integration_memoire import demarrer_memoire
        demarrer_memoire(jarvis)
    except Exception as erreur:
        print("[Mémoire] intégration indisponible :", erreur)
    jarvis.start()


if __name__ == "__main__":
    main()
