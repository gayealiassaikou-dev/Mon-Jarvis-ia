#!/usr/bin/env python3
"""
Script simple qui affiche un message de bienvenue et l'heure actuelle.
"""

from datetime import datetime

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"Bonjour de la part de Aider - il est {now}")

if __name__ == "__main__":
    main()
