#!/usr/bin/env python3
"""
Patch 2 : reponse vide d'un fournisseur IA.

Probleme : _appeler_openai_compatible faisait `return choix["content"]`.
Si content valait None, le None remontait jusqu'au reste du systeme et le
routeur n'essayait jamais le fournisseur suivant.

Correction : si la reponse est vide ET qu'aucune action d'outil n'a ete
engagee, on leve une erreur. Le routeur passe alors au fournisseur suivant.
Si une action a deja ete engagee, le comportement actuel est conserve
(protection anti-double-execution intacte).

A lancer depuis ~/Mon-Jarvis-ia :
    python3 patch2_reponse_vide.py
"""
import inspect
import os
import py_compile
import shutil
import sys

CIBLE = "core/ai_engine.py"
SAUVEGARDE = CIBLE + ".sauvegarde_patch2_reponse_vide"

ANCIEN = '                return choix["content"]\n'

NOUVEAU = '''\
                contenu = choix.get("content")

                # Reponse vide sans aucune action engagee : on leve une
                # erreur pour que le routeur essaie le fournisseur suivant.
                # Si une action a deja ete engagee, on garde le comportement
                # actuel : ni rejeu ni fallback (anti-double-execution).
                if (
                    not isinstance(contenu, str) or not contenu.strip()
                ) and not getattr(self, "action_engagee", False):
                    raise Exception(
                        "Reponse vide du fournisseur "
                        "(content absent ou vide)."
                    )

                return contenu
'''


def abandonner(message):
    print("ABANDON : " + message)
    print("Aucun fichier n'a ete modifie.")
    sys.exit(1)


def lancer_tests():
    sys.path.insert(0, os.path.abspath("core"))
    import importlib
    import types
    import ai_engine
    importlib.reload(ai_engine)

    classe = None
    for _, objet in vars(ai_engine).items():
        if inspect.isclass(objet) and hasattr(
            objet, "_appeler_openai_compatible"
        ):
            classe = objet
            break
    if classe is None:
        return [("classe", "introuvable", None)]

    class FausseReponse:
        def __init__(self, contenu):
            self.contenu = contenu

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": self.contenu}}]}

    class FauxRequests:
        contenu = None

        @staticmethod
        def post(*args, **kwargs):
            return FausseReponse(FauxRequests.contenu)

    ancien_requests = ai_engine.requests
    ai_engine.requests = FauxRequests
    echecs = []
    try:
        cas = [
            ("None, aucune action", None, False, "erreur", None),
            ("vide, aucune action", "   ", False, "erreur", None),
            ("texte normal", "Bonjour", False, "retour", "Bonjour"),
            ("None, action engagee", None, True, "retour", None),
        ]
        for nom, contenu, engagee, attendu, valeur in cas:
            FauxRequests.contenu = contenu
            faux_self = types.SimpleNamespace(action_engagee=engagee)
            try:
                resultat = classe._appeler_openai_compatible(
                    faux_self, "http://x", {}, "m", "question"
                )
                observe = ("retour", resultat)
            except Exception as e:
                observe = ("erreur", str(e))
            ok = observe[0] == attendu and (
                attendu == "erreur" or observe[1] == valeur
            )
            print(f"  [{'OK' if ok else 'ECHEC'}] {nom}")
            if not ok:
                echecs.append((nom, observe, engagee))
    finally:
        ai_engine.requests = ancien_requests
    return echecs


def main():
    if not os.path.isfile(CIBLE):
        abandonner(f"{CIBLE} introuvable (lance depuis ~/Mon-Jarvis-ia).")
    if os.path.exists(SAUVEGARDE):
        abandonner(f"la sauvegarde {SAUVEGARDE} existe deja.")

    with open(CIBLE, encoding="utf-8") as f:
        source = f.read()

    nombre = source.count(ANCIEN)
    if nombre != 1:
        abandonner(f"la ligne a remplacer est trouvee {nombre} fois (attendu : 1).")

    shutil.copyfile(CIBLE, SAUVEGARDE)
    print(f"Sauvegarde creee : {SAUVEGARDE}")

    with open(CIBLE, "w", encoding="utf-8") as f:
        f.write(source.replace(ANCIEN, NOUVEAU))

    try:
        py_compile.compile(CIBLE, doraise=True)
        print("Compilation : OK")
    except py_compile.PyCompileError as e:
        shutil.copyfile(SAUVEGARDE, CIBLE)
        print(f"Compilation ECHOUEE, fichier restaure : {e}")
        sys.exit(1)

    print("Tests :")
    try:
        echecs = lancer_tests()
    except Exception as e:
        echecs = [("import ou execution", f"{type(e).__name__}: {e}", None)]

    if echecs:
        shutil.copyfile(SAUVEGARDE, CIBLE)
        print("Tests ECHOUES, fichier restaure :")
        for nom, detail, engagee in echecs:
            print(f"  - {nom} : {detail}")
        sys.exit(1)

    print("\nPATCH 2 APPLIQUE ET TESTE.")
    print("Pour revenir en arriere : cp " + SAUVEGARDE + " " + CIBLE)


if __name__ == "__main__":
    main()
