"""Execution deterministe des actions simples - sans LLM."""
import re


def _extraire_chemin_et_contenu(objectif):
    """Detecte 'cree le fichier X contenant Y' -> (X, Y)."""
    patterns = [
        # "creer le fichier X contenant [exactement la chaine] Y"
        r"(?:cree|créé|creer|créer|ecris|écris|ecrire|écrire|crée|cree)\s+(?:un\s+|le\s+)?fichier\s+([^\s]+)\s+contenant\s+(?:exactement\s+)?(?:la\s+)?(?:chaine|chaîne|texte|contenu\s+)?\s*(.+)",
        # "... avec le contenu/texte Y"
        r"(?:cree|créé|creer|créer|ecris|écris|ecrire|écrire|crée|cree)\s+(?:un\s+|le\s+)?fichier\s+([^\s]+)\s+avec\s+(?:le\s+)?(?:contenu|texte)\s+(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, objectif, re.IGNORECASE)
        if m:
            chemin = m.group(1).strip("'\",.;")
            contenu = m.group(2).strip()
            # Enlever guillemets et texte parasite
            contenu = contenu.strip('"').strip("'").strip()
            contenu = re.sub(r'^(?:exactement\s+)?(?:la\s+)?(?:chaine|chaîne)\s+', '', contenu, flags=re.IGNORECASE)
            contenu = contenu.strip('"').strip("'").strip()
            return chemin, contenu
    return None, None


def _extraire_chemin(objectif, verbe):
    """Detecte 'verbe le fichier X' -> X."""
    pat = rf"(?:{verbe})\s+le\s+fichier\s+([^\s]+)"
    m = re.search(pat, objectif, re.IGNORECASE)
    if m:
        return m.group(1).strip("'\",.;")
    return None


def tenter(objectif):
    """Essaie d'executer l'objectif sans LLM. Retourne dict ou None."""
    if not objectif or not isinstance(objectif, str):
        return None
    obj = objectif.strip()

    # 1. Creer fichier X contenant Y
    chemin, contenu = _extraire_chemin_et_contenu(obj)
    if chemin:
        try:
            from core.tools import ecrire_fichier
            resultat = ecrire_fichier(chemin, contenu)
            return {
                "ok": True,
                "outil": "ecrire_fichier",
                "chemin": chemin,
                "contenu": contenu,
                "resultat": str(resultat)[:300],
                "message": f"Fichier {chemin} ecrit ({len(contenu)} chars) via execution deterministe.",
            }
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 2. Lire fichier X
    chemin = _extraire_chemin(obj, "lis|lire|lit|affiche|montre")
    if chemin:
        try:
            from core.tools import lire_fichier
            resultat = lire_fichier(chemin)
            return {
                "ok": True,
                "outil": "lire_fichier",
                "chemin": chemin,
                "resultat": str(resultat)[:500],
                "message": f"Contenu de {chemin} : {str(resultat)[:300]}",
            }
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 3. Supprimer fichier X
    chemin = _extraire_chemin(obj, "supprime|supprimer")
    if chemin:
        try:
            from core.tools import supprimer_fichier
            resultat = supprimer_fichier(chemin)
            return {
                "ok": True,
                "outil": "supprimer_fichier",
                "chemin": chemin,
                "resultat": str(resultat)[:300],
                "message": f"Fichier {chemin} supprime.",
            }
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    return None
