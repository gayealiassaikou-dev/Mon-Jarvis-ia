"""Test offline : le fallback ne doit pas creer espace_travail/espace_travail/."""
import os
import sys
import shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_nettoyage_contenu_espace_travail():
    """Le code extrait ne doit plus contenir 'espace_travail/' (cwd est deja dedans)."""
    # Simuler ce que le LLM renvoie typiquement
    code_brut = '''from pathlib import Path
p = Path("espace_travail")
p.mkdir(exist_ok=True)
(p / "test.txt").write_text("OK")
'''
    
    # Reproduire la logique de nettoyage appliquee dans subtask_executor
    code_nettoye = code_brut.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
    
    # Verifier que le nettoyage a bien transforme Path("espace_travail") en Path(".")
    assert '"espace_travail"' not in code_nettoye, f"Pas nettoye: {code_nettoye}"
    assert "'espace_travail'" not in code_nettoye, f"Pas nettoye: {code_nettoye}"
    assert 'Path(".")' in code_nettoye or "Path('.')" in code_nettoye


def test_pipeline_ne_cree_pas_double_dossier(tmp_path, monkeypatch):
    """Bout-en-bout : un script qui utilise Path('espace_travail') ne doit pas doubler."""
    monkeypatch.chdir(tmp_path)
    os.makedirs("espace_travail", exist_ok=True)
    
    # Code simule (comme renvoye par le LLM)
    code = '''from pathlib import Path
p = Path("espace_travail")
p.mkdir(exist_ok=True)
(p / "result.txt").write_text("DONE")
'''
    
    # Nettoyer comme dans subtask_executor
    code_clean = code.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
    
    # Ecrire et executer depuis espace_travail/ (cwd du sous-process)
    chemin_script = os.path.join("espace_travail", "_test_offline.py")
    with open(chemin_script, "w") as f:
        f.write(code_clean)
    
    import subprocess
    # Le script est dans espace_travail/, execute avec cwd=espace_travail/
    res = subprocess.run(
        [sys.executable, "_test_offline.py"],
        cwd="espace_travail",
        capture_output=True, text=True, timeout=10
    )
    
    # Verifier : le fichier doit etre dans espace_travail/, PAS dans espace_travail/espace_travail/
    assert os.path.exists(os.path.join("espace_travail", "result.txt")), \
        f"Fichier absent. stdout: {res.stdout}, stderr: {res.stderr}"
    assert not os.path.exists(os.path.join("espace_travail", "espace_travail")), \
        "Bug: espace_travail/espace_travail/ cree"
    
    # Cleanup
    shutil.rmtree("espace_travail", ignore_errors=True)


def test_code_sans_prefixe_reste_intact():
    """Un code qui n'utilise pas espace_travail/ ne doit pas etre modifie."""
    code = 'print("hello")'
    code_clean = code.replace("espace_travail/", "").replace("'espace_travail'", "'.'").replace('"espace_travail"', '"."')
    assert code_clean == code
