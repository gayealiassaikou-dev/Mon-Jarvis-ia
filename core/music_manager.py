import os
import re
import shutil
import subprocess
import unicodedata
from difflib import SequenceMatcher
from urllib.parse import quote


DOSSIER_MUSIQUE = os.path.realpath(
    os.path.expanduser("~/storage/shared")
)

FORMATS_AUDIO = {
    ".mp3", ".m4a", ".wav", ".ogg", ".flac",
    ".aac", ".opus", ".wma", ".amr", ".3gp"
}


def _normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte).casefold())
    texte = "".join(
        c for c in texte if not unicodedata.combining(c)
    )
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def _dans_telegram(chemin):
    chemin = os.path.realpath(chemin)
    parties = chemin.replace("\\", "/").split("/")
    return any(partie.casefold() == "telegram" for partie in parties)


def _rechercher_fichiers(titre):
    if not os.path.isdir(DOSSIER_MUSIQUE):
        return []

    cible = _normaliser(titre)
    if not cible:
        return []

    mots_cible = set(cible.split())
    resultats = []

    for racine, dossiers, fichiers in os.walk(
        DOSSIER_MUSIQUE,
        topdown=True,
        followlinks=False,
        onerror=lambda erreur: None
    ):
        dossiers[:] = [
            nom for nom in dossiers
            if nom.casefold() != "telegram"
            and not _dans_telegram(os.path.join(racine, nom))
        ]

        for nom in fichiers:
            chemin = os.path.join(racine, nom)

            if _dans_telegram(chemin):
                continue

            if os.path.splitext(nom)[1].casefold() not in FORMATS_AUDIO:
                continue

            if not os.path.isfile(chemin):
                continue

            nom_normalise = _normaliser(os.path.splitext(nom)[0])
            mots_fichier = set(nom_normalise.split())

            couverture = (
                len(mots_cible & mots_fichier) / len(mots_cible)
            )
            similarite = SequenceMatcher(
                None, cible, nom_normalise
            ).ratio()

            score = 0.7 * couverture + 0.3 * similarite

            if score >= 0.35:
                resultats.append((score, couverture, chemin))

    return sorted(resultats, key=lambda element: element[0], reverse=True)


def gerer_musique(titre, source="auto"):
    """Recherche et ouvre une musique locale ou une recherche en ligne."""

    titre = str(titre).strip()
    source = str(source).strip().casefold()

    if not titre or len(titre) > 200:
        return "Erreur : le titre doit contenir entre 1 et 200 caractères."

    if source not in {"auto", "local", "youtube", "spotify"}:
        return "Source inconnue. Sources disponibles : local, YouTube, Spotify."

    if source in {"auto", "local"}:
        resultats = _rechercher_fichiers(titre)

        if resultats:
            meilleur_score, couverture, chemin = resultats[0]

            if couverture == 1 and (
                len(resultats) == 1
                or meilleur_score - resultats[1][0] >= 0.08
            ):
                if _dans_telegram(chemin):
                    return "Lecture refusée : emplacement non autorisé."

                commande = shutil.which("am")
                if not commande:
                    return "Erreur : la commande Android am est indisponible."

                try:
                    uri = "file://" + quote(
                        os.path.realpath(chemin), safe="/"
                    )
                    type_audio = {
                        ".mp3": "audio/mpeg",
                        ".m4a": "audio/mp4",
                        ".wav": "audio/wav",
                        ".ogg": "audio/ogg",
                        ".flac": "audio/flac",
                        ".aac": "audio/aac",
                        ".opus": "audio/ogg",
                        ".wma": "audio/x-ms-wma",
                        ".amr": "audio/amr",
                        ".3gp": "audio/3gpp",
                    }.get(os.path.splitext(chemin)[1].lower(), "audio/*")

                    resultat = subprocess.run(
                        [
                            commande, "start",
                            "-a", "android.intent.action.VIEW",
                            "-d", uri,
                            "-t", type_audio,
                            "-p", "com.music.player.simple"
                        ],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False
                    )
                except Exception as erreur:
                    return f"Erreur pendant l'ouverture du lecteur : {erreur}"

                if resultat.returncode == 0:
                    return "Morceau envoyé au lecteur Android : " + os.path.basename(chemin)

                return "Le lecteur Android n'a pas pu ouvrir ce morceau."

            if meilleur_score >= 0.50:
                propositions = [
                    os.path.basename(element[2])
                    for element in resultats[:5]
                ]
                return (
                    "Plusieurs morceaux correspondent. "
                    "Précise le titre : " + " ; ".join(propositions)
                )

        if source == "local":
            return f"Aucun fichier audio correspondant à « {titre} »."

        source = "youtube"

    if source in {"youtube", "spotify"}:
        if source == "youtube":
            url = (
                "https://www.youtube.com/results?search_query="
                + quote(titre, safe="")
            )
            nom = "YouTube"
        else:
            url = (
                "https://open.spotify.com/search/"
                + quote(titre, safe="")
            )
            nom = "Spotify"

        commande = shutil.which("termux-open-url")
        if not commande:
            return "Erreur : termux-open-url est indisponible."

        try:
            resultat = subprocess.run(
                [commande, url],
                capture_output=True,
                text=True,
                timeout=15,
                check=False
            )
        except Exception as erreur:
            return f"Erreur lors de l'ouverture de {nom} : {erreur}"

        if resultat.returncode == 0:
            return (
                f"Recherche de « {titre} » ouverte avec {nom}. "
                "La sélection du morceau et le démarrage de la lecture "
                "peuvent nécessiter une action dans l'application."
            )

        return f"Impossible d'ouvrir la recherche {nom}."

    return "Aucune action musicale effectuée."
