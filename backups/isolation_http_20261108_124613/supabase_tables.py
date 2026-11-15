import requests

from core.supabase_memory import SupabaseMemory, SupabaseMemoryError

TIMEOUT = 20


class SupabaseTables:
    def __init__(self, memoire=None):
        self.memoire = memoire or SupabaseMemory()
        self._user_id = None

    def _entetes(self):
        return {
            "apikey": self.memoire.cle_publique,
            "Authorization": f"Bearer {self.memoire.obtenir_access_token()}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _requete(self, methode, table, params=None, donnees=None):
        try:
            r = requests.request(
                methode,
                f"{self.memoire.url}/rest/v1/{table}",
                headers=self._entetes(),
                params=params,
                json=donnees,
                timeout=TIMEOUT,
            )
        except requests.RequestException as erreur:
            raise SupabaseMemoryError(f"Réseau indisponible ({table}).") from erreur
        if not r.ok:
            raise SupabaseMemoryError(
                f"Erreur Supabase {r.status_code} sur {table} : {r.text[:200]}"
            )
        return r.json() if r.text else []

    def user_id(self):
        if self._user_id is None:
            r = requests.get(
                f"{self.memoire.url}/auth/v1/user",
                headers=self._entetes(),
                timeout=TIMEOUT,
            )
            if not r.ok:
                raise SupabaseMemoryError("Utilisateur Supabase introuvable.")
            self._user_id = r.json()["id"]
        return self._user_id

    def _inserer(self, table, donnees):
        donnees["user_id"] = self.user_id()
        return self._requete("POST", table, donnees=donnees)[0]

    def lister(self, table, ordre=None, limite=None, **filtres):
        params = {cle: f"eq.{valeur}" for cle, valeur in filtres.items()}
        if ordre:
            params["order"] = ordre
        if limite:
            params["limit"] = limite
        return self._requete("GET", table, params=params)

    def lister_tout(self, table, ordre=None, lot=500, **filtres):
        """Récupère toutes les lignes visibles par Supabase, par lots."""
        if not isinstance(lot, int) or lot < 1:
            raise ValueError("La taille du lot doit être un entier positif.")

        params = {cle: f"eq.{valeur}" for cle, valeur in filtres.items()}
        params["order"] = ordre or "id.asc"

        resultats = []
        offset = 0

        while True:
            params["limit"] = lot
            params["offset"] = offset
            lignes = self._requete("GET", table, params=params)
            resultats.extend(lignes)

            if len(lignes) < lot:
                break

            offset += lot

        return resultats

    def creer_projet(self, nom, objectif="", description="", prochaine_etape=""):
        return self._inserer("projets", {
            "nom": nom, "objectif": objectif,
            "description": description, "prochaine_etape": prochaine_etape,
        })

    def ajouter_tache(self, projet_id, titre, description="", ordre=0):
        return self._inserer("taches", {
            "projet_id": projet_id, "titre": titre,
            "description": description, "ordre": ordre,
        })

    def ajouter_point_reprise(self, projet_id, derniere_action, derniere_etape="",
                              prochaine_action="", fichiers=None, contexte="",
                              blocages=""):
        return self._inserer("points_reprise", {
            "projet_id": projet_id, "derniere_action": derniere_action,
            "derniere_etape": derniere_etape, "prochaine_action": prochaine_action,
            "fichiers_concernes": fichiers or [], "contexte_technique": contexte,
            "blocages": blocages,
        })

    def dernier_point_reprise(self, projet_id):
        lignes = self.lister("points_reprise", ordre="date_creation.desc",
                             limite=1, projet_id=projet_id)
        return lignes[0] if lignes else None

    def ajouter_historique(self, projet_id, type_evenement, description="",
                           resultat="", donnees=None):
        return self._inserer("historique_projets", {
            "projet_id": projet_id, "type_evenement": type_evenement,
            "description": description, "resultat": resultat,
            "donnees": donnees or {},
        })

    def enregistrer_quota(self, fournisseur, statut, derniere_erreur=""):
        existants = self.lister("quotas_fournisseurs", fournisseur=fournisseur)
        corps = {"statut": statut, "derniere_erreur": derniere_erreur}
        if existants:
            return self._requete(
                "PATCH", "quotas_fournisseurs",
                params={"id": f"eq.{existants[0]['id']}"}, donnees=corps,
            )[0]
        corps["fournisseur"] = fournisseur
        return self._inserer("quotas_fournisseurs", corps)
