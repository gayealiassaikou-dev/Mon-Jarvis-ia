"""Execute les sous-taches pretes d'une mission, dans l'ordre des dependances."""
import inspect
import os
import uuid

from core.mission_manager import MissionManager
from core.tool_guard import filtrer_outils_pour_agent, verifier_execution

# C4/V7 - liste blanche explicite des outils utilisables par le fallback
# hors LLM. Aucun outil du catalogue n'est appele sans figurer ici ET dans
# les permissions de l'agent de la sous-tache.
OUTILS_HORS_LLM = (
    "lire_fichier",
    "ecrire_fichier",
    "supprimer_fichier",
    "lister_fichiers",
    "creer_dossier",
    "executer_programme_python",
    "chercher_opportunites",
)

# Pseudo-outils : ils ne sont pas des outils du catalogue, mais deux
# operations gardees (ecriture puis execution) avec les permissions des
# deux outils reels correspondants.
OUTILS_SCRIPT_HORS_LLM = ("executer_script", "executer_script_python")

TAILLE_MAX_SCRIPT_HORS_LLM = 20000


def _succes_hors_llm(entree):
    """Critere unique de succes : execute ET statut succes ET verifie."""
    if not isinstance(entree, dict):
        return False
    verification = entree.get("verification") or {}
    return (
        entree.get("execute") is True
        and entree.get("statut") == "succes"
        and verification.get("verifie") is True
    )


def _outils_autorises_hors_llm(agent):
    """Liste blanche filtree par les permissions reelles de l'agent."""
    return filtrer_outils_pour_agent(agent, OUTILS_HORS_LLM)


def _valider_arguments_hors_llm(nom, arguments):
    """Refuse tout outil hors liste blanche ou tout argument inconnu."""
    if nom not in OUTILS_HORS_LLM:
        return False, f"Erreur : l'outil {nom} n'est pas autorise hors LLM."

    if not isinstance(arguments, dict):
        return False, "Erreur : les arguments doivent etre un objet."

    from core.tools_schema import FONCTIONS_DISPONIBLES

    fonction = FONCTIONS_DISPONIBLES.get(nom)
    if fonction is None:
        return False, f"Erreur : outil inconnu : {nom}."

    try:
        inspect.signature(fonction).bind(**arguments)
    except TypeError as exc:
        return (
            False,
            f"Erreur validation : argument(s) invalide(s) pour {nom} : {exc}",
        )

    return True, None


def _verifier_resultat_hors_llm(nom, arguments, resultat):
    """Verification reelle minimale pour un moteur sans point d'entree."""
    from core import tools_fichiers

    racine = getattr(
        tools_fichiers,
        "DOSSIER_AUTORISE",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    texte = str(resultat)

    if texte.startswith(("Erreur", "ECHEC", "ÉCHEC")):
        return {"verifie": False, "details": texte[:300]}

    if nom == "ecrire_fichier":
        chemin = os.path.join(racine, str(arguments.get("chemin", "")))
        try:
            with open(chemin, "r", encoding="utf-8") as fichier:
                if fichier.read() != arguments.get("contenu"):
                    return {
                        "verifie": False,
                        "details": "Contenu ecrit different du contenu demande.",
                    }
        except OSError as exc:
            return {
                "verifie": False,
                "details": f"Ecriture non verifiable : {exc}",
            }
    elif nom == "creer_dossier":
        chemin = os.path.join(racine, str(arguments.get("chemin", "")))
        if not os.path.isdir(chemin):
            return {
                "verifie": False,
                "details": "Dossier absent apres sa creation.",
            }
    elif nom == "executer_programme_python":
        premiere = texte.splitlines()[0] if texte.splitlines() else ""
        if not (premiere.startswith("SUCCES") and "code 0" in premiere):
            return {"verifie": False, "details": premiere[:300]}

    return {"verifie": True, "details": f"{nom} execute et verifie."}


def _appeler_outil_hors_llm(jarvis, nom, arguments, agent):
    """Execute un outil via le garde-fou unique, sans faux succes.

    Retourne (ok, entree, message). `ok` n'est vrai que si le resultat
    enregistre est reellement verifie.
    """
    autorises = _outils_autorises_hors_llm(agent)
    decision = verifier_execution(nom, autorises, agent=agent)
    if not decision["autorise"]:
        return False, None, f"Erreur : {decision['raison']}"

    valide, erreur = _valider_arguments_hors_llm(nom, arguments)
    if not valide:
        return False, None, erreur

    moteur = getattr(jarvis, "ai_engine", None)
    point_entree = getattr(moteur, "executer_outil_hors_llm", None)

    if callable(point_entree):
        entree = point_entree(
            nom,
            dict(arguments),
            agent=agent,
            outils_autorises=list(autorises),
        )
    else:
        # Moteur de compatibilite sans point d'entree : appel direct du
        # catalogue, mais seulement apres les memes controles de garde.
        from core.tools_schema import FONCTIONS_DISPONIBLES

        try:
            resultat = FONCTIONS_DISPONIBLES[nom](**dict(arguments))
        except Exception as exc:
            return (
                False,
                None,
                "Erreur outil : exception pendant l'execution : "
                f"{type(exc).__name__}: {exc}",
            )

        verification = _verifier_resultat_hors_llm(nom, arguments, resultat)
        entree = {
            "outil": nom,
            "arguments": dict(arguments),
            "statut": "succes" if verification["verifie"] else "echec_execution",
            "execute": True,
            "resultat": str(resultat),
            "verification": verification,
        }

    if _succes_hors_llm(entree):
        return True, entree, str(entree.get("resultat", ""))

    statut = entree.get("statut") if isinstance(entree, dict) else "inconnu"
    detail = entree.get("resultat", "") if isinstance(entree, dict) else ""
    return (
        False,
        entree,
        f"Erreur : outil {nom} non verifie ({statut}) : {str(detail)[:300]}",
    )


def _decision_script_hors_llm(agent):
    """Un script exige les permissions d'ecriture ET d'execution."""
    autorises = _outils_autorises_hors_llm(agent)
    for requis in ("ecrire_fichier", "executer_programme_python"):
        decision = verifier_execution(requis, autorises, agent=agent)
        if not decision["autorise"]:
            return {
                "autorise": False,
                "raison": f"script refuse : {decision['raison']}",
            }
    return {"autorise": True, "raison": None}


def _executer_script_hors_llm(jarvis, code, agent, identifiant):
    """Ecrit puis execute un script, avec suppression garantie en finally."""
    decision = _decision_script_hors_llm(agent)
    if not decision["autorise"]:
        return False, None, f"Erreur : {decision['raison']}"

    if not isinstance(code, str) or not code.strip():
        return False, None, "Erreur : script vide ou invalide."

    if len(code) > TAILLE_MAX_SCRIPT_HORS_LLM:
        return False, None, "Erreur : script trop volumineux pour le fallback."

    # Le script tourne deja dans espace_travail/ (cwd du programme execute).
    code = (
        code.replace("espace_travail/", "")
        .replace("'espace_travail'", "'.'")
        .replace('"espace_travail"', '"."')
    )
    chemin = f"espace_travail/_e2e_{uuid.uuid4().hex[:8]}.py"

    ok_ecriture, entree_ecriture, message = _appeler_outil_hors_llm(
        jarvis,
        "ecrire_fichier",
        {"chemin": chemin, "contenu": code + "\n"},
        agent,
    )
    if not ok_ecriture:
        return False, entree_ecriture, f"Erreur : ecriture du script impossible : {message}"

    try:
        return _appeler_outil_hors_llm(
            jarvis,
            "executer_programme_python",
            {"chemin": chemin},
            agent,
        )
    finally:
        try:
            from core.tools_fichiers import supprimer_fichier

            nettoyage = supprimer_fichier(chemin)
            if isinstance(nettoyage, str) and nettoyage.startswith("Erreur"):
                print(f"[Fallback] Nettoyage de {chemin} : {nettoyage[:150]}")
        except Exception as exc:  # noqa: BLE001 - jamais masque
            print(
                "[Fallback] Nettoyage impossible de "
                f"{chemin} : {type(exc).__name__}: {exc}"
            )


def _extraire_action_json(texte):
    """Extrait le premier objet {action, parameters} equilibre du texte."""
    import json as _json

    if not isinstance(texte, str):
        return None

    depart = 0
    while True:
        debut = texte.find("{", depart)
        if debut < 0:
            return None

        profondeur = 0
        dans_chaine = False
        echappe = False
        for i in range(debut, len(texte)):
            caractere = texte[i]
            if dans_chaine:
                if echappe:
                    echappe = False
                elif caractere == "\\":
                    echappe = True
                elif caractere == '"':
                    dans_chaine = False
                continue
            if caractere == '"':
                dans_chaine = True
            elif caractere == "{":
                profondeur += 1
            elif caractere == "}":
                profondeur -= 1
                if profondeur == 0:
                    try:
                        obj = _json.loads(texte[debut:i + 1])
                    except Exception:
                        obj = None
                    if isinstance(obj, dict) and isinstance(
                        obj.get("action"), str
                    ):
                        params = obj.get("parameters")
                        if params is None:
                            params = obj.get("parametres")
                        if not isinstance(params, dict):
                            params = {}
                        return obj["action"], params
                    depart = i + 1
                    break
        else:
            return None


def _tenter_fallback_garde(jarvis, sources, agent, identifiant):
    """Fallback JSON/code entierement garde.

    Retourne None si rien n'a ete tente, sinon (ok, entree, message).
    Aucun outil hors liste blanche n'est appele.
    """
    import re as _re

    for source in sources:
        action = _extraire_action_json(source)
        if action is None:
            continue
        nom, params = action
        if nom in OUTILS_SCRIPT_HORS_LLM:
            return _executer_script_hors_llm(
                jarvis,
                params.get("script", "") or params.get("code", ""),
                agent,
                identifiant,
            )
        return _appeler_outil_hors_llm(jarvis, nom, params, agent)

    blocs = []
    for source in sources:
        blocs.extend(
            _re.findall(r"```(?:python)?\s*\n(.+?)```", source, _re.DOTALL)
        )
    if not blocs:
        return None

    return _executer_script_hors_llm(
        jarvis, max(blocs, key=len).strip(), agent, identifiant
    )


def _pretes(sous_taches, statut_map):
    pretes = []
    for st in sous_taches:
        if st["statut"] != "nouvelle":
            continue
        deps = st.get("dependances", [])
        if all(statut_map.get(d) == "terminee" for d in deps):
            pretes.append(st)
    return pretes


def executer_mission(mission_id, max_etapes=10, auto_planifier=True):
    from core.jarvis import Jarvis
    mm = MissionManager()
    mission = mm.obtenir_mission(mission_id)
    if not mission:
        return {"erreur": "mission introuvable"}

    # Auto-planification : si la mission n'a aucune sous-tache,
    # on la decompose automatiquement avant execution.
    if auto_planifier and not mm.obtenir_sous_taches(mission_id):
        print(f"[Auto-planner] Decomposition de {mission_id}...")
        try:
            from core.mission_planner import planifier
            plan = planifier(mission_id)
            if not plan.get("ok"):
                return {
                    "erreur": f"planification echouee: {plan.get('erreur', 'inconnue')}",
                    "statut": "planification_echouee",
                }
            print(f"[Auto-planner] {plan.get('nb', 0)} sous-tache(s) creee(s).")
        except Exception as e:
            return {"erreur": f"planner exception: {type(e).__name__}: {e}"}

    jarvis = Jarvis()
    etapes = 0

    # Reinitialiser le budget de cette mission
    try:
        from core import budget_guard as _bg
        _bg.reinitialiser_mission(mission_id)
    except Exception:
        pass

    for _ in range(max_etapes):
        # Verifier le budget de la mission
        try:
            from core import budget_guard as _bg2
            _ok_m, _raison_m = _bg2.autorise_mission(mission_id)
            if not _ok_m:
                print(f"[Budget mission] {_raison_m}")
                mm.mettre_a_jour_statut(mission_id, "bloquee")
                return {"ok": False, "statut": "budget_mission", "etapes": etapes}
        except Exception:
            pass

        sous_taches = mm.obtenir_sous_taches(mission_id)
        if not sous_taches:
            return {"erreur": "aucune sous-tache apres planification", "statut": "vide"}

        statut_map = {st["id"]: st["statut"] for st in sous_taches}
        if all(s == "terminee" for s in statut_map.values()):
            mm.mettre_a_jour_statut(mission_id, "terminee")
            return {"ok": True, "etapes": etapes, "statut": "terminee"}

        pretes = _pretes(sous_taches, statut_map)
        if not pretes:
            bloquee = [s for s in statut_map.values() if s == "bloquee"]
            if bloquee:
                mm.mettre_a_jour_statut(mission_id, "bloquee")
                return {"ok": False, "statut": "bloquee", "etapes": etapes}
            return {"ok": False, "statut": "deadlock", "etapes": etapes}

        st = pretes[0]
        print(f"\n[Sous-tache {st['id']}] {st['agent']} : {st['objectif'][:80]}")
        mm.mettre_a_jour_sous_tache(mission_id, st["id"], "en_cours")

        try:
            # 1. Tentative deterministe (sans LLM) pour actions simples
            from core import deterministic_actions
            from core.tool_guard import filtrer_outils_pour_agent
            _outils_deterministes = filtrer_outils_pour_agent(
                st["agent"], deterministic_actions.OUTILS_DETERMINISTES
            )
            det = deterministic_actions.tenter(
                st["objectif"],
                agent=st["agent"],
                outils_autorises=_outils_deterministes,
            )
            if det and det.get("ok"):
                reponse = det.get("message", "OK")
                nouveaux_outils = [{"outil": det.get("outil"), "statut": "succes", "execute": True}]
                print(f"[Deterministe] {det.get('outil')} execute sans LLM")
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "terminee", resultat=reponse[:500])
                print(f"[OK] {st['id']} (deterministe)")
                etapes += 1
                continue
            # 1.5. Rejeu cristallisation : sequence d'outils deja connue ?
            try:
                from core import crystallization as _cristal
                _seq_entry = _cristal.trouver_sequence(st["objectif"])
                if _seq_entry:
                    print(f"[Cristallisation] Sequence connue ({_seq_entry.get('occurrences', 1)}x), rejeu sans LLM")
                    _rejeu = _cristal.rejouer_sequence(_seq_entry.get("sequence", []))
                    if _rejeu.get("ok"):
                        _msg_rejeu = "Sequence rejouee : " + " -> ".join(
                            [r["outil"] for r in _rejeu.get("resultats", [])]
                        )
                        mm.mettre_a_jour_sous_tache(mission_id, st["id"], "terminee", resultat=_msg_rejeu[:500])
                        print(f"[OK] {st['id']} (cristallisation)")
                        etapes += 1
                        continue
                    else:
                        print(f"[Cristallisation] Rejeu echoue ({_rejeu.get('erreur')}), passage au LLM")
            except Exception as _e_cristal:
                print(f"[Cristallisation ERREUR] {_e_cristal}")

            # 2. Sinon, pipeline LLM classique (avec conseils d'apprentissage)
            from core import learning as _learning
            objectif_enrichi = st["objectif"]
            conseils = _learning.conseils_pour(st["objectif"])
            if conseils:
                objectif_enrichi = st["objectif"] + conseils
                print(f"[Apprentissage] {conseils.count(chr(10)) - 2} conseil(s) injecte(s)")
            resultats_avant = len(jarvis.ai_engine.derniers_resultats_outils)
            reponse = jarvis.traiter_commande(objectif_enrichi, retourner_reponse=True, agent_force=st["agent"])
            nouveaux_outils = jarvis.ai_engine.derniers_resultats_outils[resultats_avant:]
            SIGNES_ECHEC = [
                "validation echouee", "je n'ai pas pu confirmer",
                "erreur ia", "aucun outil execute",
                "reussite non prouvee", "action(s) en echec",
                "je ne peux pas", "je ne suis pas en mesure",
                "que souhaitez-vous", "voulez-vous que je",
                "a votre confirmation", "quel scenario",
                "quelle option", "je ne lancerai aucune modification",
                "voulez-vous", "souhaitez-vous", "voulez vous",
                "confirmez", "attendez confirmation",
                "attends votre confirmation", "attend votre confirmation",
                "attendre votre confirmation", "j'attends votre confirmation",
                "en attente de confirmation", "avant d'agir",
                "je peux :", "je peux\u00a0:",
            ]
            # Si l'objectif demande une action concrete, la reponse doit contenir
            # une preuve d'action (pas juste du texte theorique)
            import unicodedata as _uni
            def _norm(t):
                return "".join(c for c in _uni.normalize("NFKD", str(t).lower()) if not _uni.combining(c))
            objectif_norm = _norm(st["objectif"])
            # Actions concretes qui exigent OBLIGATOIREMENT un outil
            MOTS_ACTION_CONCRETE = [
                # Fichiers
                "ecri", "cree", "creer", "modifie", "supprime",
                # Execution
                "execute", "executer", "lance", "lancer", "run",
                # Depot / installation
                "depot", "repo", "push", "commit", "installe", "telecharge",
                # Dev / implementation
                "developp", "implement", "programme", "realise", "construi",
                "genere", "produis", "code", "script",
            ]
            MOTS_RESPONSE_INFO = [
                "calcule", "calculer", "combien", "quel est", "quelle est",
                "explique", "explication", "analyse", "compare", "difference",
                "resume", "decris", "liste", "donne moi le resultat", "theorique",
            ]
            est_action_concrete = any(w in objectif_norm for w in MOTS_ACTION_CONCRETE)
            est_response_info = any(w in objectif_norm for w in MOTS_RESPONSE_INFO)
            # Forcer outil UNIQUEMENT si action concrete ET pas une simple demande de calcul/expli
            demande_action = est_action_concrete and not (
                est_response_info and not any(w in objectif_norm for w in ["ecris", "ecrire", "cree le fichier", "creer le fichier", "cree un fichier"])
            )
            rep_str = str(reponse or "").lower()
            a_repondu_texte_long = rep_str.count("\n") > 15 or len(rep_str) > 2000
            theorique_sans_action = demande_action and a_repondu_texte_long and not any(
                signe in rep_str for signe in ["fichier", "cree", "ecrit", "termine avec", "succes"]
            )
            # Reponse qui ne fait que repeter le system prompt ou le nom de l'agent
            repete_prompt = (
                len(rep_str) < 150
                and any(x in rep_str for x in ["testeur ia :", "developpeur ia :", "recherche ia :", "verifier la qualite"])
            )
            est_echec = (
                not reponse
                or not isinstance(reponse, str)
                or len(reponse.strip()) < 5
                or repete_prompt
                or any(sig in rep_str for sig in SIGNES_ECHEC)
                or theorique_sans_action
                or (demande_action and not nouveaux_outils)
            )
            # Sauvegarde reponse originale (peut contenir du code a extraire)
            reponse_originale = reponse

            # Detecter JSON action ou bloc code AVANT retry (economie quota)
            _reponse_a_code = False
            _rep_pre = str(reponse or "")
            if _rep_pre:
                if '"action"' in _rep_pre and '"parameters"' in _rep_pre:
                    _reponse_a_code = True
                elif "```python" in _rep_pre or "```" in _rep_pre:
                    _reponse_a_code = True

            # Retry force uniquement si pas de code/JSON exploitable
            if est_echec and demande_action and not nouveaux_outils and not _reponse_a_code:
                print(f"[Retry force] {st['id']} : aucun outil, on force")
                # Enrichir le retry avec les conseils d'apprentissage
                conseils_retry = ""
                try:
                    from core import learning as _learning_retry
                    _c = _learning_retry.conseils_pour(st["objectif"])
                    if _c:
                        conseils_retry = _c
                        print(f"[Retry force] + conseils d'apprentissage injectes")
                except Exception:
                    pass

                message_force = (
                    f"APPEL D'OUTIL OBLIGATOIRE. Tu dois appeler l'outil adapte pour : "
                    f"{st['objectif']}. Ne reponds pas en texte. Ne décris pas. "
                    f"Appelle directement `ecrire_fichier` (chemin + contenu) ou "
                    f"`executer_programme_python`. C'est la seule action acceptee."
                    + conseils_retry
                )
                try:
                    avant2 = len(jarvis.ai_engine.derniers_resultats_outils)
                    reponse = jarvis.traiter_commande(message_force, retourner_reponse=True, agent_force=st["agent"])
                    nouveaux_outils = jarvis.ai_engine.derniers_resultats_outils[avant2:]
                    rep_str = str(reponse or "").lower()
                    est_echec = (
                        not reponse
                        or not isinstance(reponse, str)
                        or len(reponse.strip()) < 5
                        or any(sig in rep_str for sig in SIGNES_ECHEC)
                        or (demande_action and not nouveaux_outils)
                    )
                    print(f"[Retry force] outils appeles: {len(nouveaux_outils)}, echec={est_echec}")
                except Exception as e2:
                    print(f"[Retry force ERREUR] {e2}")

            # Fallback final : JSON d'action ou bloc Python, via le garde-fou
            # unique. Aucun outil hors liste blanche, aucun faux succes.
            if est_echec and demande_action:
                _ressort = _tenter_fallback_garde(
                    jarvis,
                    [str(reponse or ""), str(reponse_originale or "")],
                    st["agent"],
                    st["id"],
                )
                if _ressort is not None:
                    _ok_fb, _entree_fb, _message_fb = _ressort
                    print(f"[Fallback] {str(_message_fb)[:200]}")
                    if _ok_fb:
                        est_echec = False
                        reponse = (
                            "Outil execute et verifie : "
                            + str(_message_fb)[:400]
                        )
                        if isinstance(_entree_fb, dict):
                            nouveaux_outils.append({
                                "outil": _entree_fb.get("outil"),
                                "arguments": _entree_fb.get("arguments", {}),
                                "statut": _entree_fb.get("statut"),
                                "execute": _entree_fb.get("execute"),
                                "verification": _entree_fb.get("verification"),
                            })
                    else:
                        reponse = str(_message_fb)

            if not est_echec:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "terminee", resultat=reponse[:500])
                try:
                    from core import learning as _learning
                    _learning.enregistrer_solution(st["objectif"], reponse[:300], st["agent"])
                except Exception:
                    pass
                # Enregistrer la sequence cristallisee pour rejeu futur
                try:
                    from core import crystallization as _cristal_save
                    _res_a_enregistrer = []
                    for _r in (nouveaux_outils or []):
                        if isinstance(_r, dict):
                            _res_a_enregistrer.append({
                                "outil": _r.get("outil"),
                                "arguments": _r.get("arguments", {}),
                                "statut": _r.get("statut"),
                                "execute": _r.get("execute"),
                            })
                    if _res_a_enregistrer:
                        _cristal_save.enregistrer_sequence(st["objectif"], _res_a_enregistrer)
                        print(f"[Cristallisation] Sequence enregistree ({len(_res_a_enregistrer)} outil(s))")
                except Exception:
                    pass
                print(f"[OK] {st['id']}")
            else:
                # Boucle apprentissage active : chercher une solution existante
                _retry_reussi = False
                try:
                    from core import learning as _learning_retry
                    _solutions = _learning_retry.conseils_pour(st["objectif"])
                    if _solutions and "SOLUTION passee" in _solutions:
                        print(f"[Apprentissage] Solution trouvee pour {st['id']}, retry intelligent...")
                        _objectif_retry = (
                            st["objectif"]
                            + "\n\nVoici une solution qui a deja fonctionne pour un objectif similaire :"
                            + _solutions
                            + "\n\nApplique cette solution directement avec un outil."
                        )
                        try:
                            avant3 = len(jarvis.ai_engine.derniers_resultats_outils)
                            _rep3 = jarvis.traiter_commande(
                                _objectif_retry,
                                retourner_reponse=True,
                                agent_force=st["agent"],
                            )
                            _new3 = jarvis.ai_engine.derniers_resultats_outils[avant3:]
                            _rep3_str = str(_rep3 or "").lower()
                            _encore_echec = (
                                not _rep3
                                or not isinstance(_rep3, str)
                                or len(_rep3.strip()) < 5
                                or any(sig in _rep3_str for sig in SIGNES_ECHEC)
                                or (demande_action and not _new3)
                            )
                            if not _encore_echec:
                                mm.mettre_a_jour_sous_tache(
                                    mission_id, st["id"], "terminee", resultat=str(_rep3)[:500]
                                )
                                _learning_retry.enregistrer_solution(
                                    st["objectif"], str(_rep3)[:300], st["agent"]
                                )
                                print(f"[OK] {st['id']} (apprentissage actif)")
                                _retry_reussi = True
                            else:
                                print(f"[Apprentissage] Retry intelligent echoue aussi")
                        except Exception as _e3:
                            print(f"[Apprentissage] Erreur retry: {_e3}")
                except Exception:
                    pass

                if not _retry_reussi:
                    mm.mettre_a_jour_sous_tache(mission_id, st["id"], "bloquee", resultat=str(reponse)[:500])
                    try:
                        from core import learning as _learning
                        _learning.enregistrer_echec(st["objectif"], str(reponse)[:200], st["agent"])
                    except Exception:
                        pass
                    print(f"[ECHEC] {st['id']} : validation reelle echouee")
                    mm.mettre_a_jour_statut(mission_id, "bloquee")
                    return {"ok": False, "statut": "bloquee", "etapes": etapes + 1, "echec_sur": st["id"]}
        except Exception as e:
            print(f"[ERREUR] {st['id']}: {type(e).__name__}: {e}")
            try:
                mm.mettre_a_jour_sous_tache(mission_id, st["id"], "bloquee", resultat=str(e)[:200])
            except Exception:
                pass
            mm.mettre_a_jour_statut(mission_id, "bloquee")
            return {"ok": False, "statut": "exception", "etapes": etapes + 1, "echec_sur": st["id"]}

        etapes += 1
        # Incrementer le compteur budget mission
        try:
            from core import budget_guard as _bg3
            _bg3.enregistrer_appel_mission(mission_id)
        except Exception:
            pass

    return {"ok": False, "statut": "max_etapes", "etapes": etapes}


if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python -m core.subtask_executor <mission_id>")
        sys.exit(1)
    print(json.dumps(executer_mission(sys.argv[1]), indent=2, ensure_ascii=False))
