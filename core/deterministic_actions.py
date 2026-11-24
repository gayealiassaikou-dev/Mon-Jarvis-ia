"""Execution deterministe des actions simples - sans LLM."""
import re

from core.tool_guard import verifier_execution


# Liste explicite des outils que le chemin deterministe peut executer.
# Aucun outil hors de cette liste ne peut etre appele ici.
OUTILS_DETERMINISTES = (
    "ecrire_fichier",
    "lire_fichier",
    "supprimer_fichier",
    "creer_dossier",
    "supprimer_dossier",
    "lister_fichiers",
    "creer_projet",
    "lister_projets",
    "lister_taches",
    "terminer_tache",
    "lampe_torche",
    "lire_batterie",
    "regler_volume",
    "lire_wifi",
)


def _refus_autorisation(nom_outil, agent, outils_autorises):
    """Retourne un refus structure, ou None si l'outil est autorise.

    Deny-by-default : sans liste explicite, ou sans l'outil dans cette
    liste, aucune execution n'est permise.
    """
    decision = verifier_execution(
        nom_outil,
        outils_autorises,
        agent=agent,
    )
    if decision["autorise"]:
        return None
    return {
        "ok": False,
        "refuse": True,
        "outil": nom_outil,
        "statut": decision["statut"],
        "code": decision["code"],
        "erreur": decision["raison"],
        "message": decision["raison"],
    }


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
            # Couper au premier " et " ou ", " ou "; " (fin de l'instruction de contenu)
            for sep in [" et s", " et v", " et p", " et d", " puis ", ", puis", "; "]:
                if sep in contenu.lower():
                    contenu = contenu[:contenu.lower().index(sep)]
            # Enlever guillemets et prefixes
            contenu = contenu.strip('"').strip("'").strip()
            contenu = re.sub(r'^(?:exactement\s+)?(?:la\s+)?(?:chaine|chaîne)\s+', '', contenu, flags=re.IGNORECASE)
            contenu = contenu.strip('"').strip("'").strip().rstrip(".,;")
            return chemin, contenu
    return None, None


def _extraire_chemin(objectif, verbe):
    """Detecte 'verbe le fichier X' -> X."""
    pat = rf"(?:{verbe})\s+le\s+fichier\s+([^\s]+)"
    m = re.search(pat, objectif, re.IGNORECASE)
    if m:
        return m.group(1).strip("'\",.;")
    return None


def tenter(objectif, agent=None, outils_autorises=None):
    """Essaie d'executer l'objectif sans LLM. Retourne dict ou None.

    `outils_autorises` est obligatoire pour toute execution : None ou []
    refuse tous les outils. `agent`, lorsqu'il est fourni, doit posseder
    l'outil dans ses permissions declarees.
    """
    if not objectif or not isinstance(objectif, str):
        return None
    obj = objectif.strip()

    # Ne pas intercepter les demandes de SCRIPT/PROGRAMME
    # (le LLM doit ecrire le code, puis le fallback l'execute)
    import re as _re_skip
    if _re_skip.search(r"\b(?:script|programme|code\s+python)\b", obj, _re_skip.IGNORECASE):
        return None

    # 1. Creer fichier X contenant Y
    chemin, contenu = _extraire_chemin_et_contenu(obj)
    if chemin:
        refus = _refus_autorisation("ecrire_fichier", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("lire_fichier", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("supprimer_fichier", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("creer_dossier", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("supprimer_dossier", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("lister_fichiers", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("creer_projet", agent, outils_autorises)
        if refus:
            return refus
        try:
            from core.tools import creer_projet
            r = creer_projet(nom)
            return {"ok": True, "outil": "creer_projet", "nom": nom,
                    "message": f"Projet '{nom}' cree. {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 8. Lister projets
    if re.search(r"(?:liste|affiche|montre)\s+(?:les\s+|mes\s+)?projets", obj, re.IGNORECASE):
        refus = _refus_autorisation("lister_projets", agent, outils_autorises)
        if refus:
            return refus
        try:
            from core.tools import lister_projets
            r = lister_projets()
            return {"ok": True, "outil": "lister_projets",
                    "message": f"Projets :\n{str(r)[:800]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 9. Lister taches
    if re.search(r"(?:liste|affiche|montre)\s+(?:les\s+|mes\s+)?taches", obj, re.IGNORECASE):
        refus = _refus_autorisation("lister_taches", agent, outils_autorises)
        if refus:
            return refus
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
        refus = _refus_autorisation("terminer_tache", agent, outils_autorises)
        if refus:
            return refus
        try:
            from core.tools import terminer_tache
            r = terminer_tache(nom)
            return {"ok": True, "outil": "terminer_tache", "nom": nom,
                    "message": f"Tache '{nom}' terminee. {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 11. Torche
    if _re_skip.search(r"\b(?:allume|active|eteins|eteindre|desactive|toggle).*torche\b|\btorche\b", obj, _re_skip.IGNORECASE):
        refus = _refus_autorisation("lampe_torche", agent, outils_autorises)
        if refus:
            return refus
        try:
            from core.actions_telephone import lampe_torche
            _etat_torche = "off" if _re_skip.search(r"\b(?:eteins|eteindre|desactive|coupe|off)\b", obj, _re_skip.IGNORECASE) else "on"
            r = lampe_torche(_etat_torche)
            return {"ok": True, "outil": "lampe_torche", "message": f"Torche: {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 12. Batterie
    if _re_skip.search(r"\bbatterie\b|\bniveau.*batterie\b", obj, _re_skip.IGNORECASE):
        refus = _refus_autorisation("lire_batterie", agent, outils_autorises)
        if refus:
            return refus
        try:
            from core.actions_telephone import lire_batterie
            r = lire_batterie()
            return {"ok": True, "outil": "lire_batterie", "message": f"Batterie: {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 13. Volume
    m = _re_skip.search(r"\bvolume\b.*?(\d{1,3})|(\d{1,3}).*?\bvolume\b", obj, _re_skip.IGNORECASE)
    if m:
        niveau = int(m.group(1) or m.group(2))
        if 0 <= niveau <= 100:
            refus = _refus_autorisation("regler_volume", agent, outils_autorises)
            if refus:
                return refus
            try:
                from core.actions_telephone import regler_volume
                # Termux : volume 0-15, on convertit depuis 0-100
                _niveau_termux = max(0, min(15, round(niveau * 15 / 100)))
                r = regler_volume(_niveau_termux)
                return {"ok": True, "outil": "regler_volume", "message": f"Volume {niveau}% (niveau {_niveau_termux}/15): {str(r)[:200]}"}
            except Exception as e:
                return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    # 14. Wi-Fi
    if _re_skip.search(r"\bwifi\b|\bwi-fi\b|\breseau\b", obj, _re_skip.IGNORECASE):
        refus = _refus_autorisation("lire_wifi", agent, outils_autorises)
        if refus:
            return refus
        try:
            from core.actions_telephone import lire_wifi
            r = lire_wifi()
            return {"ok": True, "outil": "lire_wifi", "message": f"Wi-Fi: {str(r)[:200]}"}
        except Exception as e:
            return {"ok": False, "erreur": f"{type(e).__name__}: {e}"}

    return None