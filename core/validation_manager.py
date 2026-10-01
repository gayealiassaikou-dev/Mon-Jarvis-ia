class ValidationManager:

    def __init__(self, logger):
        self.logger = logger
        self.signaux_incertitude = [
            "je ne sais pas",
            "je ne peux pas",
            "je n'ai pas acces",
            "impossible de repondre"
        ]
        self.signaux_echec_complet = [
            "erreur ia"
        ]

    def valider(self, reponse, mission_id=None, resultats_outils=None):
        if not reponse or not reponse.strip():
            return self._rejeter("Reponse vide", mission_id)

        if resultats_outils:
            echecs = [r for r in resultats_outils if str(r.get("resultat", "")).strip().lower().startswith("erreur")]
            if echecs:
                details = "; ".join(f"{r['outil']}: {r['resultat']}" for r in echecs)
                return self._rejeter(f"Action(s) en echec detectee(s) : {details}", mission_id)

        reponse_min = reponse.lower()

        if len(reponse.strip()) < 5:
            return self._rejeter("Reponse trop courte pour etre exploitable", mission_id)

        for signal in self.signaux_echec_complet:
            if signal in reponse_min:
                return self._rejeter(f"Echec complet detecte : {signal}", mission_id)

        for signal in self.signaux_incertitude:
            if signal in reponse_min:
                self.logger.enregistrer(
                    f"[Validation] Signal d'incertitude detecte : '{signal}'"
                    + (f" (mission {mission_id})" if mission_id else "")
                )
                return {
                    "valide": True,
                    "avertissement": f"Signal d'incertitude detecte : {signal}"
                }

        self.logger.enregistrer(
            "[Validation] Resultat valide"
            + (f" (mission {mission_id})" if mission_id else "")
        )
        return {"valide": True, "avertissement": None}

    def _rejeter(self, raison, mission_id=None):
        self.logger.enregistrer(
            f"[Validation] Resultat rejete : {raison}"
            + (f" (mission {mission_id})" if mission_id else "")
        )
        return {"valide": False, "avertissement": raison}
