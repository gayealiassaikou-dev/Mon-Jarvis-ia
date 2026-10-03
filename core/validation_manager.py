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

        if resultats_outils:
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

    def diagnostiquer_echec(self, validation, resultats_outils=None):
        """
        Transforme un echec de validation en diagnostic structure.

        Cette methode ne lance aucune action et ne modifie aucun outil.
        Elle sert uniquement de preparation au futur mecanisme de correction.
        """
        resultats_outils = resultats_outils or []

        if validation is None or validation.get("valide", True):
            return {
                "echec": False,
                "type": "aucun",
                "outil": None,
                "corrigeable": False,
                "raison": None
            }

        echecs_action = [
            r for r in resultats_outils
            if str(r.get("resultat", "")).strip().lower().startswith("erreur")
        ]

        if echecs_action:
            premier = echecs_action[0]
            return {
                "echec": True,
                "type": "action",
                "outil": premier.get("outil"),
                "corrigeable": False,
                "raison": validation.get(
                    "avertissement",
                    "Une action d'outil a echoue."
                )
            }

        echecs_verification = [
            r for r in resultats_outils
            if isinstance(r.get("verification"), dict)
            and r["verification"].get("verifie") is False
        ]

        if echecs_verification:
            premier = echecs_verification[0]
            verification = premier.get("verification", {})
            return {
                "echec": True,
                "type": "verification",
                "outil": premier.get("outil"),
                "corrigeable": False,
                "raison": verification.get(
                    "details",
                    validation.get(
                        "avertissement",
                        "La verification de l'action a echoue."
                    )
                )
            }

        return {
            "echec": True,
            "type": "reponse",
            "outil": None,
            "corrigeable": False,
            "raison": validation.get(
                "avertissement",
                "La validation de la reponse a echoue."
            )
        }

    def autoriser_correction(self, diagnostic, resultats_outils=None):
        """
        Determine si une correction automatique est autorisee.
        Cette methode ne execute aucun outil.
        """
        resultats_outils = resultats_outils or []

        if not isinstance(diagnostic, dict):
            return {
                "autorisee": False,
                "raison": "Diagnostic invalide."
            }

        if not diagnostic.get("echec", False):
            return {
                "autorisee": False,
                "raison": "Aucun echec a corriger."
            }

        outil = diagnostic.get("outil")

        if not outil:
            return {
                "autorisee": False,
                "raison": "Aucun outil identifie pour la correction."
            }

        outils_interdits = {
            "supprimer_fichier",
            "supprimer_tache",
            "supprimer_projet",
            "github_ecrire_fichier",
            "memoriser_info"
        }

        if outil in outils_interdits:
            return {
                "autorisee": False,
                "raison": (
                    f"Correction automatique interdite pour "
                    f"l'outil destructif ou externe '{outil}'."
                )
            }

        outils_rejouables = {
            "ecrire_fichier"
        }

        if outil not in outils_rejouables:
            return {
                "autorisee": False,
                "raison": (
                    f"Aucune politique de correction automatique "
                    f"definie pour l'outil '{outil}'."
                )
            }

        if diagnostic.get("type") != "verification":
            return {
                "autorisee": False,
                "raison": (
                    "La correction automatique est actuellement "
                    "limitee aux echecs de verification."
                )
            }

        correspondances = [
            resultat
            for resultat in resultats_outils
            if resultat.get("outil") == outil
        ]

        if not correspondances:
            return {
                "autorisee": False,
                "raison": (
                    f"Aucun resultat enregistre pour l'outil '{outil}'."
                )
            }

        self.logger.enregistrer(
            f"[Validation] Correction automatique autorisee pour '{outil}'."
        )

        return {
            "autorisee": True,
            "raison": (
                f"L'outil '{outil}' est autorise a etre rejoue "
                "une seule fois par la future boucle de correction."
            )
        }

    def _rejeter(self, raison, mission_id=None):
        self.logger.enregistrer(
            f"[Validation] Resultat rejete : {raison}"
            + (f" (mission {mission_id})" if mission_id else "")
        )
        return {"valide": False, "avertissement": raison}
