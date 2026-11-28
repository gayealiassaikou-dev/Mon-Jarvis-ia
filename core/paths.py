"""Chemins centraux du projet Sam Sarr.

``DATA_DIR`` et ``MEMORY_DIR`` suivent la resolution de ``core.chemins``
(variables ``JARVIS_DATA_DIR`` / ``JARVIS_MEMORY_DIR``), afin qu'il n'existe
qu'une seule source de verite pour les chemins de donnees.
"""

from pathlib import Path

from core import chemins

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = Path(chemins.dossier_donnees())
MEMORY_DIR = Path(chemins.dossier_memoire())
ENV_FILE = PROJECT_ROOT / ".env"
