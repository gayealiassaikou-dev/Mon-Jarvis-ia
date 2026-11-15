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

    # 4. Creer un dossier
    m = re.search(r"(?:cree|creer|créé|créer)\s+(?:le\s+|un\s+)?dossier\s+([^\s]+)", obj, re.IGNORECASE)
    if m:
        chemin = m.group(1).strip("'\",.;")
        try:
            from core.tools import creer_dossier
            r = creer_dossier(chemin)
            return {"ok": True, "outil": "creer_dossier", "chemin": chemin,
                    "message": f"Dossier {chemin} cree. {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 5. Supprimer un dossier
    m = re.search(r"supprime(?:r)?\s+(?:le\s+|un\s+)?dossier\s+([^\s]+)", obj, re.IGNORECASE)
    if m:
        chemin = m.group(1).strip("'\",.;")
        try:
            from core.tools import supprimer_dossier
            r = supprimer_dossier(chemin)
            return {"ok": True, "outil": "supprimer_dossier", "chemin": chemin,
                    "message": f"Dossier {chemin} supprime. {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 6. Lister un dossier
    m = re.search(r"(?:liste|affiche|montre)\s+(?:les\s+)?(?:fichiers?|contenu)\s+(?:de\s+|du\s+|dans\s+)?([^\s]*)", obj, re.IGNORECASE)
    if m:
        dossier = (m.group(1) or ".").strip("'\",.;") or "."
        try:
            from core.tools import lister_fichiers
            r = lister_fichiers(dossier)
            return {"ok": True, "outil": "lister_fichiers", "dossier": dossier,
                    "message": f"Contenu de {dossier} :\n{str(r)[:500]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 7. Creer un projet
    m = re.search(r"(?:cree|creer|créé|créer)\s+(?:le\s+|un\s+)?projet\s+(.+)", obj, re.IGNORECASE)
    if m:
        nom = m.group(1).strip("'\",.;")
        try:
            from core.tools import creer_projet
            r = creer_projet(nom)
            return {"ok": True, "outil": "creer_projet", "nom": nom,
                    "message": f"Projet '{nom}' cree. {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 8. Lister projets
    if re.search(r"(?:liste|affiche|montre)\s+(?:les\s+|mes\s+)?projets", obj, re.IGNORECASE):
        try:
            from core.tools import lister_projets
            r = lister_projets()
            return {"ok": True, "outil": "lister_projets",
                    "message": f"Projets :\n{str(r)[:800]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 9. Lister taches
    if re.search(r"(?:liste|affiche|montre)\s+(?:les\s+|mes\s+)?taches", obj, re.IGNORECASE):
        try:
            from core.tools import lister_taches
            r = lister_taches()
            return {"ok": True, "outil": "lister_taches",
                    "message": f"Taches :\n{str(r)[:800]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 10. Terminer une tache
    m = re.search(r"(?:termine|terminer|finis|finir)\s+(?:la\s+)?tache\s+(.+)", obj, re.IGNORECASE)
    if m:
        nom = m.group(1).strip("'\",.;")
        try:
            from core.tools import terminer_tache
            r = terminer_tache(nom)
            return {"ok": True, "outil": "terminer_tache", "nom": nom,
                    "message": f"Tache '{nom}' terminee. {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    return None