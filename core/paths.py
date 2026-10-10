"""Chemins centraux du projet Samba Sarr."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_DIR = PROJECT_ROOT / "memory"
ENV_FILE = PROJECT_ROOT / ".env"
