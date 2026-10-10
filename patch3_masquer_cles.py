#!/usr/bin/env python3
"""
Patch 3 : masquer les cles API dans les messages d'erreur du routeur.

Probleme : une erreur HTTP de Gemini contient l'URL complete, cle
comprise (...?key=XXXX). Le routeur renvoyait ce texte tel quel, donc
il s'affichait a l'ecran, dans les logs et dans la memoire.

Correction : une fonction masquer_secrets() remplace la valeur des cles
par *** dans tout message d'erreur renvoye par AIRouter.

A lancer depuis ~/Mon-Jarvis-ia :
    python3 patch3_masquer_cles.py
"""
import os
import py_compile
import shutil
import sys

CIBLE = "core/ai_router.py"
SAUVEGARDE = CIBLE + ".sauvegarde_patch3_masquer_cles"

# Remplacements : (ancien, nouveau). Chaque ancien doit exister 1 fois.
REMPLACEMENTS = [
    (
        "import time\n",
        '''\
import re
import time


def masquer_secrets(texte):
    """Remplace les cles API visibles dans un message d'erreur."""
    texte = str(texte)
    texte = re.sub(
        r"(?i)([?&](?:key|api_key|apikey|token|access_token)=)"
        r"[^&\\s'\\"]+",
        r"\\1***",
        texte,
    )
    texte = re.sub(
        r"(?i)(bearer\\s+)[A-Za-z0-9._~+/=-]{8,}",
        r"\\1***",
        texte,
    )
    return texte
''',
    ),
    (
        '                    f"{fournisseur}: {str(e)}"\n',
        '                    f"{fournisseur}: {masquer_secrets(str(e))}"\n',
    ),
    (
        '                        f"{type(e).__name__}: {e}. "\n',
        '                        f"{type(e).__name__}: {masquer_secrets(str(e))}. "\n',
    ),
]


def abandonner(message):
    print("ABANDON : " + message)
    print("Aucun fichier n'a ete modifie.")
    sys.exit(1)


def lancer_tests():
    sys.path.insert(0, os.path.abspath("core"))
    import importlib
    import ai_router
    importlib.reload(ai_router)

    fausse_cle = "AQ.FAUSSECLE1234567890abcdef"
    echecs = []

    def verifier(nom, condition):
        print(f"  [{'OK' if condition else 'ECHEC'}] {nom}")
        if not condition:
            echecs.append(nom)

    url = (
        "429 Client Error: Too Many Requests for url: "
        f"https://exemple.test/v1/m:generate?key={fausse_cle}"
    )
    masque = ai_router.masquer_secrets(url)
    verifier("cle d'URL masquee", fausse_cle not in masque and "key=***" in masque)

    masque = ai_router.masquer_secrets("a=1&api_key=" + fausse_cle + "&b=2")
    verifier("cle au milieu de l'URL", fausse_cle not in masque and "&b=2" in masque)

    masque = ai_router.masquer_secrets("Authorization: Bearer " + fausse_cle)
    verifier("jeton Bearer masque", fausse_cle not in masque)

    normal = "Erreur : fichier introuvable"
    verifier("texte normal inchange", ai_router.masquer_secrets(normal) == normal)

    class FauxMoteur:
        def __init__(self, engagee):
            self.action_engagee = engagee

        def _echec(self, *a, **k):
            raise Exception(url)

        _demander_groq = _echec
        _demander_gemini = _echec
        _demander_openrouter = _echec
        _demander_mistral = _echec

    sortie = ai_router.AIRouter(FauxMoteur(False)).demander("question")
    verifier(
        "routeur : toutes les IA en echec, cle masquee",
        fausse_cle not in sortie and "Toutes les IA" in sortie,
    )

    sortie = ai_router.AIRouter(FauxMoteur(True)).demander("question")
    verifier(
        "routeur : action engagee, cle masquee",
        fausse_cle not in sortie and "Fallback automatique" in sortie,
    )
    return echecs


def main():
    if not os.path.isfile(CIBLE):
        abandonner(f"{CIBLE} introuvable (lance depuis ~/Mon-Jarvis-ia).")
    if os.path.exists(SAUVEGARDE):
        abandonner(f"la sauvegarde {SAUVEGARDE} existe deja.")

    with open(CIBLE, encoding="utf-8") as f:
        source = f.read()

    for ancien, _ in REMPLACEMENTS:
        nombre = source.count(ancien)
        if nombre != 1:
            abandonner(
                f"la ligne {ancien.strip()!r} est trouvee {nombre} fois "
                "(attendu : 1)."
            )

    shutil.copyfile(CIBLE, SAUVEGARDE)
    print(f"Sauvegarde creee : {SAUVEGARDE}")

    nouveau = source
    for ancien, remplacement in REMPLACEMENTS:
        nouveau = nouveau.replace(ancien, remplacement)
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
    try:
        echecs = lancer_tests()
    except Exception as e:
        echecs = [f"import ou execution : {type(e).__name__}: {e}"]

    if echecs:
        shutil.copyfile(SAUVEGARDE, CIBLE)
        print("Tests ECHOUES, fichier restaure :")
        for nom in echecs:
            print(f"  - {nom}")
        sys.exit(1)

    print("\nPATCH 3 APPLIQUE ET TESTE.")
    print("Pour revenir en arriere : cp " + SAUVEGARDE + " " + CIBLE)


if __name__ == "__main__":
    main()
