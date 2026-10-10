#!/usr/bin/env python3
"""Diagnostic Python en lecture seule : vérifie la syntaxe des fichiers."""

import ast
import sys
from pathlib import Path


RACINE = Path(__file__).resolve().parent.parent


def verifier_syntaxe(chemin):
    try:
        source = chemin.read_text(encoding="utf-8")
        ast.parse(source, filename=str(chemin))
        return True, "Syntaxe valide"
    except SyntaxError as exc:
        return False, f"Syntaxe invalide ligne {exc.lineno}: {exc.msg}"
    except (OSError, UnicodeError) as exc:
        return False, f"Lecture impossible : {type(exc).__name__}: {exc}"


def main():
    chemins = [
        chemin
        for chemin in sys.argv[1:]
    ]

    if not chemins:
        print(
            "Utilisation : python tests/diagnostic_python.py "
            "fichier.py [autre_fichier.py ...]"
        )
        return 2

    erreurs = 0

    for nom in chemins:
        chemin = (RACINE / nom).resolve()

        try:
            chemin.relative_to(RACINE)
        except ValueError:
            print(f"[REFUS] Chemin hors du projet : {nom}")
            erreurs += 1
            continue

        if not chemin.is_file() or chemin.suffix != ".py":
            print(f"[REFUS] Fichier Python introuvable ou invalide : {nom}")
            erreurs += 1
            continue

        ok, message = verifier_syntaxe(chemin)
        etiquette = "OK" if ok else "ERREUR"
        print(f"[{etiquette}] {nom} : {message}")

        if not ok:
            erreurs += 1

    print(f"\nBilan : {erreurs} erreur(s) sur {len(chemins)} fichier(s).")
    return 1 if erreurs else 0


if __name__ == "__main__":
    raise SystemExit(main())
