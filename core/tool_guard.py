"""Garde-fou central des permissions d'outils.

Politique unique, appliquee avant toute execution d'outil :

- un outil doit etre connu ;
- une liste d'outils explicitement autorises doit etre fournie
  (None ou [] refusent tout : deny-by-default) ;
- l'outil doit figurer dans cette liste ;
- si un agent est fourni, il doit exister et avoir l'outil dans
  ses permissions.

Ce module ne remplace pas les protections propres aux outils
(chemins autorises, fichiers proteges, suppression explicite).
Il centralise uniquement la decision de permission.
"""
from core.agent_permissions import PERMISSIONS_AGENTS, TOUS_LES_OUTILS

OUTILS_MEMOIRE = frozenset({"memoriser_info", "rechercher_souvenir"})
OUTILS_CONNUS = frozenset(TOUS_LES_OUTILS) | OUTILS_MEMOIRE

STATUT_AUTORISE = "autorise"
STATUT_NON_AUTORISE = "non_autorise"
STATUT_OUTIL_INCONNU = "outil_inconnu"


def outil_connu(nom_fonction):
    """Vrai si l'outil est declare dans le catalogue du projet."""
    if not isinstance(nom_fonction, str) or not nom_fonction.strip():
        return False
    nom = nom_fonction.strip()
    if nom in OUTILS_CONNUS:
        return True
    # Verification de coherence avec le catalogue executoire.
    try:
        from core.tools_schema import FONCTIONS_DISPONIBLES
    except Exception:
        return False
    return nom in FONCTIONS_DISPONIBLES


def permissions_agent(agent):
    """Permissions declares de l'agent, ou ensemble vide si inconnu."""
    if not isinstance(agent, str) or agent not in PERMISSIONS_AGENTS:
        return frozenset()
    return frozenset(PERMISSIONS_AGENTS[agent])


def _refus(statut, raison, code):
    return {
        "autorise": False,
        "statut": statut,
        "raison": raison,
        "code": code,
    }


def verifier_execution(nom_fonction, outils_autorises=None, agent=None):
    """Decide si un outil peut etre execute.

    Retourne un dictionnaire : autorise, statut, raison, code.
    Aucun effet de bord : cette fonction ne fait que decider.
    """
    nom = nom_fonction.strip() if isinstance(nom_fonction, str) else ""

    if not outil_connu(nom):
        return _refus(
            STATUT_OUTIL_INCONNU,
            f"Outil inconnu : {nom_fonction}.",
            "outil_inconnu",
        )

    if not isinstance(outils_autorises, (list, tuple, set)) or not outils_autorises:
        return _refus(
            STATUT_NON_AUTORISE,
            f"L'outil {nom} n'est pas autorise pour cette execution.",
            "aucun_outil_autorise",
        )

    if nom not in outils_autorises:
        return _refus(
            STATUT_NON_AUTORISE,
            f"L'outil {nom} n'est pas autorise pour cette execution.",
            "outil_non_liste",
        )

    if agent is not None:
        if not isinstance(agent, str) or agent not in PERMISSIONS_AGENTS:
            return _refus(
                STATUT_NON_AUTORISE,
                f"Agent inconnu : {agent}.",
                "agent_inconnu",
            )
        if nom not in PERMISSIONS_AGENTS[agent]:
            return _refus(
                STATUT_NON_AUTORISE,
                f"L'outil {nom} n'est pas autorise pour l'agent {agent}.",
                "hors_permissions_agent",
            )

    return {
        "autorise": True,
        "statut": STATUT_AUTORISE,
        "raison": None,
        "code": "autorise",
    }


def filtrer_outils_pour_agent(agent, outils_suggeres):
    """Ne conserve que les outils suggeres autorises pour l'agent.

    Agent inconnu -> aucun outil. L'ordre d'origine est conserve.
    """
    if not isinstance(agent, str) or agent not in PERMISSIONS_AGENTS:
        return []
    if not isinstance(outils_suggeres, (list, tuple, set)):
        return []

    autorises = PERMISSIONS_AGENTS[agent]
    return [
        outil for outil in outils_suggeres
        if isinstance(outil, str) and outil in autorises
    ]
