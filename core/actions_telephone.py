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
        plugged = data.get("plugged", "")
        branchee = "sur batterie" if plugged == "UNPLUGGED" else "branchee"
        return f"Batterie : {percent} % {branchee}"
    except (json.JSONDecodeError, TypeError):
        return "Erreur : impossible d'analyser la réponse de la batterie."


def regler_volume(niveau):
    """Règle le volume du flux music entre 0 et le maximum disponible."""
    if not isinstance(niveau, int):
        return "Erreur : le niveau doit être un entier."

    # Obtenir le volume actuel et le maximum
    info_output = _run_command(["termux-volume"])
    if isinstance(info_output, tuple):
        return info_output[1]

    try:
        info = json.loads(info_output)
        music_info = next((item for item in info if item.get("stream") == "music"), None)
        if not music_info:
            return "Erreur : impossible d'obtenir le volume du flux music."
        max_vol = music_info.get("max_volume")
    except Exception:
        return "Erreur : impossible d'obtenir le volume maximal."

    if not (0 <= niveau <= max_vol):
        return f"Erreur : le niveau doit être entre 0 et {max_vol}."

    # Régler le volume
    set_result = _run_command(["termux-volume", "music", str(niveau)])
    if isinstance(set_result, tuple):
        return set_result[1]

    # Vérifier la valeur réglée
    verify_output = _run_command(["termux-volume"])
    if isinstance(verify_output, tuple):
        return verify_output[1]

    try:
        verify_info = json.loads(verify_output)
        music_verify = next((item for item in verify_info if item.get("stream") == "music"), None)
        if not music_verify:
            return "Erreur : impossible de vérifier le volume."
        cur = music_verify.get("volume")
        max_vol_check = music_verify.get("max_volume")
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

def regler_luminosite(niveau):
    """Règle la luminosité de l'écran entre 0 et 255 via termux-brightness."""
    if not isinstance(niveau, int):
        return "Erreur : le niveau doit être un entier."
    if not (0 <= niveau <= 255):
        return f"Erreur : le niveau doit être entre 0 et 255."
    result = _run_command(["termux-brightness", str(niveau)])
    if isinstance(result, tuple):
        return result[1]
    return f"Luminosite regle : {niveau}"


def lire_wifi():
    """Lit les informations de connexion Wi‑Fi via termux-wifi-connectioninfo."""
    output = _run_command(["termux-wifi-connectioninfo"])
    if isinstance(output, tuple):
        return output[1]
    try:
        data = json.loads(output)
        ssid = data.get("ssid", "Inconnu")
        bssid = data.get("bssid", "")
        ip = data.get("ip", "")
        return f"Wi-Fi : SSID={ssid}, BSSID={bssid}, IP={ip}"
    except (json.JSONDecodeError, TypeError):
        return "Erreur : impossible d'analyser les informations Wi‑Fi."


def lire_notifications():
    """Liste les notifications récentes via termux-notification-list (max 10)."""
    output = _run_command(["termux-notification-list"])
    if isinstance(output, tuple):
        return output[1]
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return "Erreur : format de réponse inattendu."
        lines = []
        for i, notif in enumerate(data[:10], 1):
            title = notif.get("title", "")
            text = notif.get("text", "")
            lines.append(f"{i}. {title}: {text}")
        if not lines:
            return "Notifications : aucune."
        return "Notifications : " + " | ".join(lines)
    except (json.JSONDecodeError, TypeError):
        return "Erreur : impossible d'analyser la liste des notifications."
