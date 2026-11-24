"""Schemas des outils pour Jarvis - extrait de ai_engine.py."""
import os
import requests

from core.business_intel import chercher_opportunites
from core.tools import (
    definir_projet_actif, obtenir_projet_actif, executer_tests_python,
    executer_programme_python, reparer_syntaxe_python, diagnostiquer_code_python,
    analyser_erreur_python, corriger_code_python, lire_fichier, ecrire_fichier,
    creer_parent_manquant_pour_ecriture, supprimer_fichier, supprimer_dossier,
    lister_fichiers, creer_dossier, rechercher_web, creer_projet, ajouter_tache,
    lister_projets, lister_taches, terminer_tache, supprimer_tache,
    supprimer_projet, modifier_statut_projet, github_lister_repos,
    github_lire_fichier, github_ecrire_fichier, github_creer_repo,
    lire_etat_projets_taches,
)
from core.music_manager import gerer_musique
from core.outils_telephone import (
    SCHEMAS_TELEPHONE, FONCTIONS_TELEPHONE, verifier_action_telephone,
)

OUTILS = [
    {
        "type": "function",
        "function": {
            "name": "chercher_opportunites",
            "description": "Cherche des opportunites business rentables pour une niche (redaction, code, traduction, data). Retourne prix marche + sources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "niche": {"type": "string", "description": "Niche: redaction, code, traduction ou data"}
                },
                "required": ["niche"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lire_fichier",
            "description": "Lit le contenu d'un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a lire"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ecrire_fichier",
            "description": "Ecrit ou remplace un fichier en utilisant un chemin relatif a la racine du depot. Inclure le sous-dossier du projet cible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif depuis la racine du depot, sous-dossier du projet inclus, par exemple Dandé Lenol/saikou/gaye.txt"},
                    "contenu": {"type": "string", "description": "Contenu a ecrire dans le fichier"}
                },
                "required": ["chemin", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_fichier",
            "description": "Supprime definitivement un fichier du projet",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif du fichier a supprimer"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_dossier",
            "description": "Supprime definitivement un dossier et tout son contenu. Utiliser uniquement sur demande explicite de l'utilisateur, avec le chemin exact. Ne jamais supprimer la racine du projet ni un chemin protege.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif exact du dossier a supprimer depuis la racine du projet"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_fichiers",
            "description": "Recherche et liste les fichiers et dossiers du projet. Si le chemin exact est introuvable, examine les chemins proches proposés dans le résultat. Si la cible est un fichier, appelle lire_fichier avec son chemin exact pour lire son contenu. Si la cible est un dossier, appelle lister_fichiers avec le chemin exact pour explorer son contenu. Enchaîne les appels nécessaires au lieu de t’arrêter à une simple suggestion. Ne prétends jamais avoir lu un fichier sans résultat de lecture.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dossier": {"type": "string", "description": "Chemin relatif du dossier a lister, par defaut le dossier racine"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creer_dossier",
            "description": "Cree un dossier avec un chemin relatif a la racine du depot. Inclure le sous-dossier du projet cible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin relatif depuis la racine du depot, sous-dossier du projet inclus si necessaire."}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_creer_repo",
            "description": "Cree un depot GitHub avec l'authentification locale gh et verifie son existence",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {
                        "type": "string",
                        "description": "Nom du nouveau depot GitHub"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description du depot"
                    },
                    "public": {
                        "type": "boolean",
                        "description": "True pour un depot public, False pour un depot prive"
                    }
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_lister_repos",
            "description": "Liste les depots GitHub de l'utilisateur",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_lire_fichier",
            "description": "Lit le contenu d'un fichier depuis un depot GitHub",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Nom complet du depot, format utilisateur/repo"},
                    "chemin": {"type": "string", "description": "Chemin du fichier dans le depot"}
                },
                "required": ["repo", "chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "github_ecrire_fichier",
            "description": "Cree ou met a jour un fichier dans un depot GitHub avec un commit",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Nom du depot GitHub. Le nom simple du depot est suffisant, par exemple Dande-Lenol. Si seul le nom du depot est fourni, l outil determine automatiquement le compte GitHub authentifie. Le format utilisateur/repo est aussi accepte."},
                    "chemin": {"type": "string", "description": "Chemin du fichier dans le depot"},
                    "contenu": {"type": "string", "description": "Nouveau contenu du fichier"},
                    "message": {"type": "string", "description": "Message du commit"}
                },
                "required": ["repo", "chemin", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memoriser_info",
            "description": "Enregistre une information importante en memoire longue duree pour s en souvenir plus tard",
            "parameters": {
                "type": "object",
                "properties": {
                    "categorie": {"type": "string", "description": "Categorie: projets, decisions, preferences, connaissances ou erreurs"},
                    "contenu": {"type": "string", "description": "L information a memoriser"}
                },
                "required": ["categorie", "contenu"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_souvenir",
            "description": "Recherche une information precedemment memorisee",
            "parameters": {
                "type": "object",
                "properties": {
                    "mot_cle": {"type": "string", "description": "Mot-cle a rechercher dans la memoire"}
                },
                "required": ["mot_cle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rechercher_web",
            "description": "Recherche des informations actuelles sur internet",
            "parameters": {
                "type": "object",
                "properties": {
                    "requete": {"type": "string", "description": "La requete de recherche"}
                },
                "required": ["requete"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "creer_projet",
            "description": "Cree un nouveau projet dans le suivi de Jarvis",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet a creer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ajouter_tache",
            "description": "Ajoute une nouvelle tache dans le suivi de Jarvis",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache"},
                    "projet": {"type": "string", "description": "Le projet associe, optionnel"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "definir_projet_actif",
            "description": "Selectionne explicitement le projet sur lequel travailler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Nom exact du projet existant"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtenir_projet_actif",
            "description": "Indique quel projet est actuellement selectionne.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_projets",
            "description": "Liste tous les projets enregistres",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lister_taches",
            "description": "Liste toutes les taches enregistrees",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminer_tache",
            "description": "Marque une tache comme terminee",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache a terminer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_tache",
            "description": "Supprime une tache du suivi",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom de la tache a supprimer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "supprimer_projet",
            "description": "Supprime un projet du suivi",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet a supprimer"}
                },
                "required": ["nom"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modifier_statut_projet",
            "description": "Modifie le statut d'un projet (en cours, en pause, termine, annule)",
            "parameters": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string", "description": "Le nom du projet"},
                    "nouveau_statut": {"type": "string", "description": "Le nouveau statut : en cours, en pause, termine ou annule"}
                },
                "required": ["nom", "nouveau_statut"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "corriger_code_python",
            "description": "Applique une correction exacte a un fichier Python uniquement si le nouveau code passe la verification syntaxique.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string"},
                    "ancien_code": {"type": "string"},
                    "nouveau_code": {"type": "string"}
                },
                "required": ["chemin", "ancien_code", "nouveau_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reparer_syntaxe_python",
            "description": "Repare localement certaines erreurs de syntaxe Python simples, puis verifie le fichier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin du fichier Python a reparer"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyser_erreur_python",
            "description": "Analyse un traceback Python et explique localement le type d'erreur, le fichier, la ligne et sa cause probable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "traceback": {"type": "string", "description": "Traceback complet retourne par l'execution Python"}
                },
                "required": ["traceback"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "diagnostiquer_code_python",
            "description": "Analyse localement la syntaxe d'un fichier Python et indique les erreurs et leurs lignes, sans executer le code ni appeler une IA externe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin du fichier Python a analyser"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "executer_tests_python",
            "description": "Lance la suite complete des tests Python du depot et retourne les resultats reels.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "executer_programme_python",
            "description": "Execute un programme Python present dans espace_travail et retourne sa sortie et ses erreurs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chemin": {"type": "string", "description": "Chemin du fichier Python dans espace_travail"}
                },
                "required": ["chemin"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "gerer_musique",
            "description": "Recherche et lance un morceau de musique localement, sur YouTube ou Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titre": {
                        "type": "string",
                        "description": "Titre ou nom du morceau recherché"
                    },
                    "source": {
                        "type": "string",
                        "enum": ["auto", "local", "youtube", "spotify"],
                        "description": "Source musicale. auto recherche localement puis sur YouTube."
                    }
                },
                "required": ["titre"]
            }
        }
    }
]

# Outils sans effet de bord : ils n'engagent pas d'action, donc le
# routeur peut essayer un autre fournisseur sans risque de double execution.
OUTILS_LECTURE_SEULE = frozenset({
    "lire_fichier", "lister_fichiers", "lister_projets", "lister_taches",
    "obtenir_projet_actif",
    "rechercher_web", "rechercher_souvenir",
    "github_lister_repos", "github_lire_fichier", "lire_pdf", "lire_page_web",
})

FONCTIONS_DISPONIBLES = {
    "lire_fichier": lire_fichier,
    "ecrire_fichier": ecrire_fichier,
    "supprimer_fichier": supprimer_fichier,
    "supprimer_dossier": supprimer_dossier,
    "lister_fichiers": lister_fichiers,
    "creer_dossier": creer_dossier,
    "github_creer_repo": github_creer_repo,
    "github_lister_repos": github_lister_repos,
    "github_lire_fichier": github_lire_fichier,
    "github_ecrire_fichier": github_ecrire_fichier,
    "rechercher_web": rechercher_web,
    "definir_projet_actif": definir_projet_actif,
    "obtenir_projet_actif": obtenir_projet_actif,
    "creer_projet": creer_projet,
    "ajouter_tache": ajouter_tache,
    "lister_projets": lister_projets,
    "lister_taches": lister_taches,
    "terminer_tache": terminer_tache,
    "supprimer_tache": supprimer_tache,
    "supprimer_projet": supprimer_projet,
    "modifier_statut_projet": modifier_statut_projet,
    "reparer_syntaxe_python": reparer_syntaxe_python,
    "analyser_erreur_python": analyser_erreur_python,
    "diagnostiquer_code_python": diagnostiquer_code_python,
    "corriger_code_python": corriger_code_python,
    "executer_tests_python": executer_tests_python,
    "executer_programme_python": executer_programme_python,
    "gerer_musique": gerer_musique,
    "chercher_opportunites": chercher_opportunites
}
from core.tools_pdf import lire_pdf
OUTILS.append({
    "type": "function",
    "function": {
        "name": "lire_pdf",
        "description": "Lit le texte d'un fichier PDF du projet (20 pages max par appel). Utilise page_debut pour lire la suite. Ne jamais pretendre avoir lu un PDF sans resultat de lecture.",
        "parameters": {
            "type": "object",
            "properties": {
                "chemin": {"type": "string", "description": "Chemin relatif du fichier .pdf"},
                "page_debut": {"type": "integer", "description": "Premiere page a lire (defaut 1)"}
            },
            "required": ["chemin"]
        }
    }
})
FONCTIONS_DISPONIBLES["lire_pdf"] = lire_pdf
from core.tools_navigation import lire_page_web
OUTILS.append({
    "type": "function",
    "function": {
        "name": "lire_page_web",
        "description": "Ouvre une page web (http/https) et en lit le texte. Utiliser apres rechercher_web pour lire une source en detail. Ne jamais pretendre avoir lu une page sans resultat de lecture.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Adresse complete de la page, commencant par http:// ou https://"}
            },
            "required": ["url"]
        }
    }
})
FONCTIONS_DISPONIBLES["lire_page_web"] = lire_page_web
OUTILS.extend(SCHEMAS_TELEPHONE)
FONCTIONS_DISPONIBLES.update(FONCTIONS_TELEPHONE)


def _convertir_outils_gemini(outils):
    declarations = []
    for outil in outils:
        fonction = outil["function"]
        declarations.append({
            "name": fonction["name"],
            "description": fonction["description"],
            "parameters": fonction["parameters"]
        })
    return [{"functionDeclarations": declarations}]


OUTILS_GEMINI = _convertir_outils_gemini(OUTILS)
