
from core.actions_telephone import (
    lire_batterie,
    regler_volume,
    lampe_torche,
    envoyer_notification,
    lire_presse_papiers,
    regler_luminosite,
    lire_wifi,
    lire_notifications,
)

# Schémas OpenAI pour les fonctions téléphoniques
SCHEMAS_TELEPHONE = [
    {
        "type": "function",
        "function": {
            "name": "lire_batterie",
            "description": "Lit le statut de la batterie du téléphone via Termux.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "regler_volume",
            "description": "Règle le volume du flux musical du téléphone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "niveau": {
                        "type": "integer",
                        "description": "Niveau de volume souhaité (entre 0 et le maximum).",
                    },
                },
                "required": ["niveau"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lampe_torche",
            "description": "Allume ou éteint la lampe torche du téléphone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "etat": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "État désiré de la lampe torche.",
                    },
                },
                "required": ["etat"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "envoyer_notification",
            "description": "Envoie une notification sur le téléphone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titre": {
                        "type": "string",
                        "description": "Titre de la notification (max 80 caractères).",
                    },
                    "texte": {
                        "type": "string",
                        "description": "Corps du texte de la notification (max 200 caractères).",
                    },
                },
                "required": ["titre", "texte"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lire_presse_papiers",
            "description": "Lit le contenu du presse‑papiers du téléphone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "regler_luminosite",
            "description": "Règle la luminosité de l'écran entre 0 et 255.",
            "parameters": {
                "type": "object",
                "properties": {
                    "niveau": {
                        "type": "integer",
                        "description": "Niveau de luminosité (0-255).",
                    },
                },
                "required": ["niveau"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lire_wifi",
            "description": "Lit les informations de connexion Wi‑Fi du téléphone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lire_notifications",
            "description": "Liste les notifications récentes du téléphone.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

# Mapping des noms de fonctions vers leurs implémentations réelles
FONCTIONS_TELEPHONE = {
    "lire_batterie": lire_batterie,
    "regler_volume": regler_volume,
    "lampe_torche": lampe_torche,
    "envoyer_notification": envoyer_notification,
    "lire_presse_papiers": lire_presse_papiers,
    "regler_luminosite": regler_luminosite,
    "lire_wifi": lire_wifi,
    "lire_notifications": lire_notifications,
}


def verifier_action_telephone(nom_fonction, resultat):
    """
    Vérifie que le résultat d'une fonction téléphonique commence par le préfixe attendu.

    Args:
        nom_fonction (str): Nom de la fonction appelée.
        resultat (str): Texte retourné par la fonction.

    Returns:
        dict: {'verifie': bool, 'details': str}
    """
    prefixes = {
        "lire_batterie": "Batterie :",
        "regler_volume": "Volume regle :",
        "lampe_torche": "Lampe torche :",
        "envoyer_notification": "Notification envoyee :",
        "lire_presse_papiers": "Presse-papiers :",
        "regler_luminosite": "Luminosite regle :",
        "lire_wifi": "Wi-Fi :",
        "lire_notifications": "Notifications :",
    }

    expected = prefixes.get(nom_fonction)
    if expected is None:
        return {"verifie": False, "details": f"Fonction inconnue '{nom_fonction}'."}

    if isinstance(resultat, str) and resultat.startswith(expected):
        return {
            "verifie": True,
            "details": f"Le résultat commence bien par le préfixe attendu '{expected}'.",
        }
    else:
        return {
            "verifie": False,
            "details": f"Le résultat ne commence pas par le préfixe attendu '{expected}'. Résultat reçu: {resultat!r}",
        }
