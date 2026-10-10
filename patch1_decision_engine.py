#!/usr/bin/env python3
"""
Patch 1 : DecisionEngine sans outils + validation de la reponse du LLM.

A lancer depuis ~/Mon-Jarvis-ia :
    python3 patch1_decision_engine.py

Sequence : verifications -> sauvegarde -> modification -> compilation -> tests.
Si la compilation ou un test echoue, le fichier d'origine est restaure.
"""
import glob
import os
import py_compile
import re
import shutil
import sys

CIBLE = "core/decision_engine.py"
SAUVEGARDE = CIBLE + ".sauvegarde_patch1_decision"

# --- Remplacement 1 : appel du LLM sans outils ---------------------------
ANCIEN_APPEL = (
    "            reponse = self.ai_engine.router.demander(prompt)\n"
)

NOUVEL_APPEL = '''\
            # Appel sans aucun outil : la decision ne doit jamais
            # executer d'action. ai_engine.demander remet aussi a zero
            # action_engagee avant l'appel.
            reponse = self.ai_engine.demander(
                prompt,
                outils_autorises=[],
                mode_action=False,
            )

            if not isinstance(reponse, str) or not reponse.strip():
                raise ValueError(
                    "Reponse du LLM vide ou invalide : "
                    f"{type(reponse).__name__}"
                )
'''

# --- Remplacement 2 : lecture du JSON avec trace de la reponse brute -----
ANCIEN_JSON = "            data = json.loads(reponse_nettoyee)\n"

NOUVEAU_JSON = '''\
            try:
                data = json.loads(reponse_nettoyee)
            except json.JSONDecodeError:
                print(
                    "[DecisionEngine] Reponse non JSON : "
                    f"{reponse[:300]!r}"
                )
                raise

            if not isinstance(data, dict):
                raise ValueError(
                    "La decision du LLM n'est pas un objet JSON."
                )
'''


def abandonner(message):
    print("ABANDON : " + message)
    print("Aucun fichier n'a ete modifie.")
    sys.exit(1)


def verifier_appelants():
    """Refuse de patcher si decider/choisir_agent sont appeles ailleurs
    que dans le flux normal de jarvis.py (risque de remettre
    action_engagee a zero en pleine mission)."""
    suspects = []
    for chemin in glob.glob("core/*.py"):
        if chemin.endswith("decision_engine.py"):
            continue
        with open(chemin, encoding="utf-8") as f:
            for numero, ligne in enumerate(f, 1):
                if re.search(r"\.decider\(|choisir_agent\(", ligne):
                    if "decision_engine.decider(commande)" in ligne:
                        continue
                    suspects.append(f"{chemin}:{numero}: {ligne.strip()}")
    if suspects:
        abandonner(
            "appels inattendus du DecisionEngine :\n  "
            + "\n  ".join(suspects)
        )


def lancer_tests():
    sys.path.insert(0, os.path.abspath("core"))
    import importlib
    import decision_engine
    importlib.reload(decision_engine)

    valide = (
        '{"agent": "01_developpeur", "difficulte": "faible", '
        '"risques": "faible", "validation_requise": true, '
        '"resume": "test", "outils_suggeres": '
        '["ecrire_fichier", "outil_inexistant"]}'
    )

    class FauxAgents:
        agents = {"00_directeur_ia": "", "01_developpeur": ""}

    class FauxIA:
        def __init__(self, reponse):
            self.reponse = reponse
            self.appels = []

        def demander(self, message, contexte="", historique=None,
                     outils_autorises=None, mode_action=False):
            self.appels.append((outils_autorises, mode_action))
            return self.reponse

    cas = [
        ("None", None, "00_directeur_ia", []),
        ("vide", "", "00_directeur_ia", []),
        ("texte non JSON", "Toutes les IA sont indisponibles : x",
         "00_directeur_ia", []),
        ("JSON qui est une liste", "[1, 2]", "00_directeur_ia", []),
        ("JSON valide", valide, "01_developpeur", ["ecrire_fichier"]),
        ("JSON avec balises", "```json\n" + valide + "\n```",
         "01_developpeur", ["ecrire_fichier"]),
    ]

    echecs = []
    for nom, reponse, agent_attendu, outils_attendus in cas:
        ia = FauxIA(reponse)
        moteur = decision_engine.DecisionEngine(None, FauxAgents(), ia)
        try:
            d = moteur.decider("Cree test.py")
            ok = (
                d["agent"] == agent_attendu
                and d["outils_suggeres"] == outils_attendus
                and ia.appels == [([], False)]
            )
        except Exception as e:
            ok = False
            d = f"exception {type(e).__name__}: {e}"
        print(f"  [{'OK' if ok else 'ECHEC'}] {nom}")
        if not ok:
            echecs.append((nom, d, ia.appels))
    return echecs


def main():
    if not os.path.isfile(CIBLE):
        abandonner(f"{CIBLE} introuvable (lance le script depuis ~/Mon-Jarvis-ia).")
    if os.path.exists(SAUVEGARDE):
        abandonner(f"la sauvegarde {SAUVEGARDE} existe deja (patch deja applique ?).")

    verifier_appelants()

    with open(CIBLE, encoding="utf-8") as f:
        source = f.read()

    for nom, ancien in (("appel LLM", ANCIEN_APPEL), ("lecture JSON", ANCIEN_JSON)):
        nombre = source.count(ancien)
        if nombre != 1:
            abandonner(f"la ligne '{nom}' est trouvee {nombre} fois (attendu : 1).")

    shutil.copyfile(CIBLE, SAUVEGARDE)
    print(f"Sauvegarde creee : {SAUVEGARDE}")

    nouveau = source.replace(ANCIEN_APPEL, NOUVEL_APPEL)
    nouveau = nouveau.replace(ANCIEN_JSON, NOUVEAU_JSON)
    with open(CIBLE, "w", encoding="utf-8") as f:
        f.write(nouveau)

    try:
        py_compile.compile(CIBLE, doraise=True)
        print("Compilation : OK")
    except py_compile.PyCompileError as e:
        shutil.copyfile(SAUVEGARDE, CIBLE)
        print(f"Compilation ECHOUEE, fichier restaure : {e}")
        sys.exit(1)

    print("Tests :")
    echecs = lancer_tests()
    if echecs:
        shutil.copyfile(SAUVEGARDE, CIBLE)
        print("Tests ECHOUES, fichier restaure :")
        for nom, d, appels in echecs:
            print(f"  - {nom} : {d} / appels={appels}")
        sys.exit(1)

    print("\nPATCH 1 APPLIQUE ET TESTE.")
    print("Pour revenir en arriere : cp " + SAUVEGARDE + " " + CIBLE)


if __name__ == "__main__":
    main()
