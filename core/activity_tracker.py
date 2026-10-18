"""Suivi sécurisé des activités de Sam Sarr pour l'interface web."""

from collections import OrderedDict, deque
from datetime import datetime, timezone
from threading import RLock


class ActivityTracker:
    """Conserve la progression de chaque demande en mémoire."""

    def __init__(self, max_demandes=100, max_etapes=100):
        self._demandes = OrderedDict()
        self._verrou = RLock()
        self._max_demandes = max_demandes
        self._max_etapes = max_etapes

    @staticmethod
    def _maintenant():
        return datetime.now(timezone.utc).isoformat()

    def demarrer(self, demande_id):
        if not isinstance(demande_id, str) or not demande_id:
            raise ValueError("Identifiant de demande invalide.")

        with self._verrou:
            self._demandes[demande_id] = {
                "id": demande_id,
                "etat": "en_cours",
                "debut": self._maintenant(),
                "fin": None,
                "etapes": deque(maxlen=self._max_etapes),
            }
            while len(self._demandes) > self._max_demandes:
                ancien_id = next(iter(self._demandes))
                if self._demandes[ancien_id]["etat"] == "en_cours":
                    demandes_terminees = [
                        identifiant
                        for identifiant, demande in self._demandes.items()
                        if demande["etat"] != "en_cours"
                    ]
                    if not demandes_terminees:
                        break
                    del self._demandes[demandes_terminees[0]]
                else:
                    del self._demandes[ancien_id]

        self.ajouter_etape(demande_id, "Demande reçue", "en_cours")

    def ajouter_etape(self, demande_id, message, statut="information"):
        messages_autorises = {
            "Demande reçue",
            "Analyse de la demande",
            "Choix de l'agent",
            "Préparation du contexte",
            "Appel du moteur IA",
            "Exécution d'un outil",
            "Vérification du résultat",
            "Validation de la réponse",
            "Réponse préparée",
            "Demande terminée",
            "Demande échouée",
        }

        if message not in messages_autorises:
            message = "Activité en cours"

        if statut not in {
            "information", "en_cours", "succes", "echec"
        }:
            statut = "information"

        with self._verrou:
            demande = self._demandes.get(demande_id)
            if demande is None:
                return False

            demande["etapes"].append({
                "heure": self._maintenant(),
                "message": message,
                "statut": statut,
            })
            return True

    def terminer(self, demande_id, succes=True):
        with self._verrou:
            demande = self._demandes.get(demande_id)
            if demande is None:
                return False

            demande["etat"] = "terminee" if succes else "echec"
            demande["fin"] = self._maintenant()
            demande["etapes"].append({
                "heure": demande["fin"],
                "message": (
                    "Demande terminée" if succes
                    else "Demande échouée"
                ),
                "statut": "succes" if succes else "echec",
            })
            return True

    def consulter(self, demande_id):
        with self._verrou:
            demande = self._demandes.get(demande_id)
            if demande is None:
                return None

            return {
                "id": demande["id"],
                "etat": demande["etat"],
                "debut": demande["debut"],
                "fin": demande["fin"],
                "etapes": list(demande["etapes"]),
            }
