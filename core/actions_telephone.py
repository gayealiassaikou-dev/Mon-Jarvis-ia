import json
import subprocess


def _run_command(cmd):
    """Execute a Termux command with a 10‑second timeout."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return None, "Erreur : délai d'attente dépassé."
    except subprocess.CalledProcessError as e:
        return None, f"Erreur : la commande a échoué ({e})."
    except Exception as e:
        return None, f"Erreur : {e}."


def lire_batterie():
    """Lit le statut de la batterie via termux‑battery‑status."""
    output = _run_command(["termux-battery-status"])
    if isinstance(output, tuple):
        return output[1]

    try:
        data = json.loads(output)
        percent = data.get("percentage")
        status = data.get("status", "").lower()
        branchee = "branchee" if "charging" in status else "sur batterie"
        return f"Batterie : {percent} % {branchee}"
    except (json.JSONDecodeError, TypeError):
        return "Erreur : impossible d'analyser la réponse de la batterie."


def regler_volume(niveau):
    """Règle le volume du flux music entre 0 et le maximum disponible."""
    if not isinstance(niveau, int):
        return "Erreur : le niveau doit être un entier."

    # Obtenir le volume actuel et le maximum
    max_output = _run_command(["termux-volume", "music"])
    if isinstance(max_output, tuple):
        return max_output[1]

    try:
        # termux-volume renvoie quelque chose comme "volume: X/Y"
        parts = max_output.split()
        cur_max = parts[-1]            # "X/Y"
        _, max_vol = map(int, cur_max.split("/"))
    except Exception:
        return "Erreur : impossible d'obtenir le volume maximal."

    if not (0 <= niveau <= max_vol):
        return f"Erreur : le niveau doit être entre 0 et {max_vol}."

    # Régler le volume
    set_result = _run_command(["termux-volume", "music", str(niveau)])
    if isinstance(set_result, tuple):
        return set_result[1]

    # Vérifier la valeur réglée
    verify_output = _run_command(["termux-volume", "music"])
    if isinstance(verify_output, tuple):
        return verify_output[1]

    try:
        parts = verify_output.split()
        cur_max = parts[-1]
        cur, max_vol_check = map(int, cur_max.split("/"))
    except Exception:
        return "Erreur : impossible de vérifier le volume."

    if cur == niveau:
        return f"Volume regle : {cur} sur {max_vol_check}"
    else:
        return "Erreur : le volume réglé ne correspond pas à la valeur demandée."


def lampe_torche(etat):
    """Allume ou éteint la lampe torche."""
    if etat not in ("on", "off"):
        return "Erreur : état invalide, utilisez 'on' ou 'off'."

    result = _run_command(["termux-torch", etat])
    if isinstance(result, tuple):
        return result[1]

    return f"Lampe torche : {'allumee' if etat == 'on' else 'eteinte'}"


def envoyer_notification(titre, texte):
    """Envoie une notification via termux‑notification."""
    if not isinstance(titre, str) or not isinstance(texte, str):
        return "Erreur : titre et texte doivent être des chaînes."

    titre_coupe = titre[:80]
    texte_coupe = texte[:200]

    result = _run_command(
        ["termux-notification", "-t", titre_coupe, "-c", texte_coupe]
    )
    if isinstance(result, tuple):
        return result[1]

    return f"Notification envoyee : {titre_coupe}"


def lire_presse_papiers():
    """Lit le contenu du presse‑papiers."""
    output = _run_command(["termux-clipboard-get"])
    if isinstance(output, tuple):
        return output[1]

    texte_coupe = output[:500]
    return f"Presse-papiers : {texte_coupe}"


if __name__ == "__main__":
    print(lire_batterie())
