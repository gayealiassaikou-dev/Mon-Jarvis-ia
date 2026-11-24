"""Outil creer_site_web : genere un site statique dans espace_travail/<nom>/."""
import os
import re

from core.tools_fichiers import DOSSIER_AUTORISE, _chemin_autorise, _fichier_protege


def _nom_valide(nom):
    if not isinstance(nom, str):
        return None
    n = nom.strip().lower()
    if not re.match(r"^[a-z0-9_-]{1,40}$", n):
        return None
    return n


def creer_site_web(nom, titre="Mon site", description="Site cree par Jarvis"):
    """Cree espace_travail/<nom>/index.html + style.css + script.js et verifie."""
    n = _nom_valide(nom)
    if not n:
        return "Erreur : nom invalide (a-z, 0-9, - ou _, max 40)."

    dossier = os.path.abspath(os.path.join(DOSSIER_AUTORISE, "espace_travail", n))
    if not _chemin_autorise(dossier):
        return "Erreur : chemin refuse."
    if _fichier_protege(dossier):
        return "Erreur : dossier protege."

    if os.path.exists(dossier):
        return f"Erreur : le site '{n}' existe deja."

    try:
        os.makedirs(dossier, exist_ok=True)

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header><h1>{titre}</h1><p>{description}</p></header>
<main>
<section>
<h2>Bienvenue</h2>
<p>Ce site a ete genere par Jarvis.</p>
<button id="btn">Clique-moi</button>
<p id="msg"></p>
</section>
</main>
<footer><p>&copy; 2026 - {titre}</p></footer>
<script src="script.js"></script>
</body>
</html>
"""

        css = """* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; line-height: 1.6; color: #222; background: #fafafa; }
header { background: #4fc3f7; color: #fff; padding: 2rem 1rem; text-align: center; }
main { max-width: 720px; margin: 2rem auto; padding: 0 1rem; }
section { background: #fff; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
h2 { margin-bottom: 1rem; color: #0277bd; }
button { background: #4fc3f7; color: #fff; border: 0; padding: 0.6rem 1.2rem; border-radius: 4px; cursor: pointer; }
button:hover { background: #0288d1; }
footer { text-align: center; padding: 2rem; color: #666; font-size: 0.9rem; }
"""

        js = """document.getElementById('btn').addEventListener('click', function() {
  document.getElementById('msg').textContent = 'Bouton clique a ' + new Date().toLocaleTimeString();
});
"""

        fichiers = {"index.html": html, "style.css": css, "script.js": js}
        for nom_f, contenu in fichiers.items():
            chemin_f = os.path.join(dossier, nom_f)
            with open(chemin_f, "w", encoding="utf-8") as f:
                f.write(contenu)

        # Verification
        manquants = [nom_f for nom_f in fichiers if not os.path.isfile(os.path.join(dossier, nom_f))]
        if manquants:
            return f"Erreur : fichiers manquants apres creation : {manquants}"

        return (
            f"Site '{n}' cree et verifie : index.html, style.css, script.js "
            f"dans espace_travail/{n}/ ({len(html)+len(css)+len(js)} octets)."
        )
    except Exception as e:
        return f"Erreur creation site : {type(e).__name__}: {e}"
