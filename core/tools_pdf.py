import os
from core.tools_fichiers import DOSSIER_AUTORISE, _chemin_autorise, _fichier_protege

MAX_PAGES = 20
MAX_CARACTERES = 15000


def lire_pdf(chemin, page_debut=1):
    chemin_complet = os.path.abspath(os.path.join(DOSSIER_AUTORISE, chemin))
    if not _chemin_autorise(chemin_complet):
        return "Erreur : accès refusé en dehors du projet."
    chemin_reel = os.path.realpath(chemin_complet)
    if not _chemin_autorise(chemin_reel):
        return "Erreur : accès refusé en dehors du projet."
    if _fichier_protege(chemin_reel):
        return "Erreur : accès refusé, fichier ou dossier protégé."
    if not os.path.isfile(chemin_reel):
        return f"Erreur : le fichier {chemin} n'existe pas."
    if not chemin_reel.lower().endswith(".pdf"):
        return "Erreur : ce n'est pas un fichier .pdf."
    try:
        from pypdf import PdfReader
        lecteur = PdfReader(chemin_reel)
        if lecteur.is_encrypted:
            return "Erreur : PDF chiffré, lecture impossible."
        total = len(lecteur.pages)
        debut = max(1, int(page_debut))
        if debut > total:
            return f"Erreur : le PDF a seulement {total} page(s)."
        fin = min(total, debut + MAX_PAGES - 1)
        morceaux = []
        for i in range(debut - 1, fin):
            morceaux.append(f"--- Page {i + 1}/{total} ---\n" + (lecteur.pages[i].extract_text() or ""))
        texte = "\n".join(morceaux).strip()
        if not texte.replace("-", "").strip():
            return "Erreur : aucun texte extractible (PDF scanné ou image ?)."
        if len(texte) > MAX_CARACTERES:
            texte = texte[:MAX_CARACTERES] + "\n[... texte tronqué]"
        return texte
    except Exception as exc:
        return f"Erreur : impossible de lire le PDF : {exc}"
