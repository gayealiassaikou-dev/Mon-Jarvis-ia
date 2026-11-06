import os, re, sys, unicodedata

DOSSIER = os.path.expanduser("~/storage/shared/VidMate/download")
EXT = (".mp3", ".m4a", ".opus", ".ogg", ".wav", ".mp4")

def mots(texte):
    texte = unicodedata.normalize("NFD", texte.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texte).split()

def chercher(requete):
    voulus = mots(requete)
    if not voulus:
        return None
    meilleur = None
    for racine, _, fichiers in os.walk(DOSSIER, followlinks=True):
        for nom in fichiers:
            if not nom.lower().endswith(EXT):
                continue
            ensemble = " ".join(mots(nom))
            if all(m in ensemble for m in voulus):
                chemin = os.path.join(racine, nom)
                if meilleur is None or len(nom) < len(os.path.basename(meilleur)):
                    meilleur = chemin
    return meilleur

if __name__ == "__main__":
    trouve = chercher(" ".join(sys.argv[1:]))
    if trouve:
        print(trouve)
        sys.exit(0)
    sys.exit(1)
