#!/usr/bin/env python3
"""Genere etat_actuel/carte_projet.md (lecture seule sur le code)."""

import ast
import re
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CORE = RACINE / "core"
TESTS = RACINE / "tests"
SORTIE = RACINE / "etat_actuel" / "carte_projet.md"


def analyser(chemin):
    source = chemin.read_text(encoding="utf-8")
    arbre = ast.parse(source, filename=str(chemin))
    classes, fonctions = [], []
    for noeud in arbre.body:
        if isinstance(noeud, ast.ClassDef):
            classes.append(noeud.name)
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fonctions.append(noeud.name)
    return len(source.splitlines()), classes, fonctions


def tests_pour(module):
    trouves = []
    motif = re.compile(r"from core import .*\b" + re.escape(module) + r"\b")
    for t in sorted(TESTS.glob("test_*.py")):
        texte = t.read_text(encoding="utf-8")
        if f"core.{module}" in texte or motif.search(texte):
            trouves.append(t.name)
    return trouves


def main():
    lignes = ["# Carte du projet", "", f"Generee le {datetime.now():%Y-%m-%d %H:%M}", ""]
    sans_tests = []
    for chemin in sorted(CORE.glob("*.py")):
        try:
            n, classes, fonctions = analyser(chemin)
        except (SyntaxError, OSError, UnicodeError) as exc:
            lignes += [f"## core/{chemin.name}", f"- Analyse impossible : {exc}", ""]
            continue
        tests = tests_pour(chemin.stem)
        if not tests:
            sans_tests.append(chemin.name)
        lignes.append(f"## core/{chemin.name} ({n} lignes)")
        lignes.append("- Classes : " + (", ".join(classes) or "aucune"))
        lignes.append("- Fonctions : " + (", ".join(fonctions) or "aucune"))
        lignes.append("- Tests : " + (", ".join(tests) or "AUCUN"))
        lignes.append("")
    lignes.append("## Modules sans test dans tests/")
    lignes += [f"- {nom}" for nom in sans_tests] or ["- aucun"]
    lignes.append("")
    hors = sorted(p.name for p in RACINE.glob("test_*.py"))
    lignes.append("## Fichiers test_*.py a la racine (hors tests/)")
    lignes += [f"- {nom}" for nom in hors] or ["- aucun"]
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"Carte ecrite : {SORTIE}")
    print(f"Modules sans test : {len(sans_tests)}")


if __name__ == "__main__":
    main()
