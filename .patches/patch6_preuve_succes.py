from pathlib import Path
import py_compile
import shutil

ROOT = Path.cwd()
AI = ROOT / "core" / "ai_engine.py"
VM = ROOT / "core" / "validation_manager.py"

AI_BACKUP = ROOT / "core" / "ai_engine.py.sauvegarde_patch6_preuve"
VM_BACKUP = ROOT / "core" / "validation_manager.py.sauvegarde_patch6_preuve"

if not AI.exists() or not VM.exists():
    raise SystemExit("ERREUR: fichier source introuvable.")

if not AI_BACKUP.exists() or not VM_BACKUP.exists():
    raise SystemExit("ERREUR: sauvegardes Patch 6 introuvables.")

ai = AI.read_text(encoding="utf-8")
vm = VM.read_text(encoding="utf-8")

ancien_ai = '''        if not execute:
            statut = "echec_execution"
        elif isinstance(verification, dict) and verification.get("verifie") is False:
            statut = "verification_echec"
        elif str(resultat).startswith("Erreur"):
            statut = "echec_execution"
        else:
            statut = "succes"
'''

nouveau_ai = '''        if not execute:
            statut = "echec_execution"
        elif str(resultat).startswith("Erreur"):
            statut = "echec_execution"
        elif (
            isinstance(verification, dict)
            and verification.get("verifie") is True
        ):
            statut = "succes"
        else:
            statut = "verification_echec"
'''

ancien_vm = '''        if resultats_outils:
            echecs_verification = [
                r for r in resultats_outils
                if isinstance(r.get("verification"), dict)
                and r["verification"].get("verifie") is False
            ]
            if echecs_verification:
                details = "; ".join(
                    f"{r['outil']}: "
                    f"{r['verification'].get('details', 'Verification echouee.')}"
                    for r in echecs_verification
                )
                return self._rejeter(
                    f"Verification d'action echouee : {details}",
                    mission_id
                )
'''

nouveau_vm = '''        if resultats_outils:
            preuves_absentes = [
                r for r in resultats_outils
                if r.get("execute") is True
                and not (
                    isinstance(r.get("verification"), dict)
                    and r["verification"].get("verifie") is True
                )
            ]
            if preuves_absentes:
                details = "; ".join(
                    f"{r.get('outil', 'outil inconnu')}: "
                    f"{(
                        r.get('verification', {}).get(
                            'details',
                            'Preuve de succes absente.'
                        )
                        if isinstance(r.get('verification'), dict)
                        else 'Preuve de succes absente.'
                    )}"
                    for r in preuves_absentes
                )
                return self._rejeter(
                    f"Preuve de succes absente ou invalide : {details}",
                    mission_id
                )

            echecs_verification = [
                r for r in resultats_outils
                if isinstance(r.get("verification"), dict)
                and r["verification"].get("verifie") is False
            ]
            if echecs_verification:
                details = "; ".join(
                    f"{r['outil']}: "
                    f"{r['verification'].get('details', 'Verification echouee.')}"
                    for r in echecs_verification
                )
                return self._rejeter(
                    f"Verification d'action echouee : {details}",
                    mission_id
                )
'''

if ancien_ai not in ai:
    raise SystemExit(
        "ERREUR: bloc AIEngine attendu introuvable ou Patch 6 deja applique."
    )

if ancien_vm not in vm:
    raise SystemExit(
        "ERREUR: bloc ValidationManager attendu introuvable ou Patch 6 deja applique."
    )

AI.write_text(ai.replace(ancien_ai, nouveau_ai, 1), encoding="utf-8")
VM.write_text(vm.replace(ancien_vm, nouveau_vm, 1), encoding="utf-8")

try:
    py_compile.compile(str(AI), doraise=True)
    py_compile.compile(str(VM), doraise=True)
except Exception:
    shutil.copy2(AI_BACKUP, AI)
    shutil.copy2(VM_BACKUP, VM)
    raise

print("PATCH6_MODIFICATION_OK")
print("Compilation Python : OK")
