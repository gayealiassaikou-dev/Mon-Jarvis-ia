"""Tests offline des actions deterministes (0 appel LLM)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.deterministic_actions import tenter


def test_fichier_simple():
    r = tenter("Ecris le fichier espace_travail/_test_det.txt contenant SimpleOK")
    assert r and r["ok"]
    assert r["contenu"] == "SimpleOK", f"Contenu: {r['contenu']!r}"
    os.remove("espace_travail/_test_det.txt")


def test_fichier_avec_suffixe():
    r = tenter('Créer le fichier "espace_travail/_test2.txt" contenant exactement la chaîne "OK2" et s\'assurer qu\'il est enregistre')
    assert r and r["ok"]
    assert r["contenu"] == "OK2", f"Contenu: {r['contenu']!r}"
    os.remove("espace_travail/_test2.txt")


def test_script_pas_deterministe():
    """Les demandes de script passent au LLM, pas au deterministe."""
    r = tenter("Developpe un script Python qui cree X")
    assert r is None, f"Ne devrait pas intercepter: {r}"


def test_dossier():
    r = tenter("cree le dossier espace_travail/_test_dir")
    assert r and r["ok"]
    assert os.path.isdir("espace_travail/_test_dir")
    os.rmdir("espace_travail/_test_dir")


def test_liste_projets():
    r = tenter("liste les projets")
    assert r and r["ok"]
    assert "Projets" in r["message"]
