import unicodedata

CATEGORIES_ERREUR = [
    ("verification_echouee", ["verification echouee"]),
    ("deja_existant", ["existe deja"]),
    ("introuvable", ["n'existe pas", "introuvable"]),
    ("acces_refuse", ["acces refuse", "protege", "refusee"]),
    ("service_externe", ["timeout", "impossible de se connecter",
                         "limite de requetes"]),
    ("authentification", ["cle api", "token"]),
    ("argument_invalide", ["invalide", "doit etre", "obligatoire",
                           "trop long", "pas un fichier",
                           "pas un dossier"]),
]


def classer_erreur(texte):
    # Deduit une categorie de cause a partir du message (sans accents).
    brut = unicodedata.normalize("NFKD", str(texte or ""))
    brut = "".join(c for c in brut if not unicodedata.combining(c))
    brut = brut.lower()
    for categorie, mots in CATEGORIES_ERREUR:
        if any(mot in brut for mot in mots):
            return categorie
    return "inconnue"


class ValidationManager:

    def __init__(self, logger):
        self.logger = logger

        # Une seule correction automatique autorisée par demande.
        self.corrections_utilisees = 0
        self.max_corrections = 1

        self.signaux_incertitude = [
            "je ne sais pas",
            "je ne peux pas",
            "je n'ai pas acces",
            "impossible de repondre"
        ]
        self.signaux_echec_complet = [
            "erreur ia"
        ]

    def valider(self, reponse, mission_id=None, resultats_outils=None,
                outils_attendus=False):
        if not reponse or not reponse.strip():
            return self._rejeter("Reponse vide", mission_id)

        # Une mission qui attendait des outils ne peut pas etre validee
        # sans aucun resultat d'outil : le texte du modele n'est pas une preuve.
        if outils_attendus and mission_id and not resultats_outils:
            return self._rejeter(
                "Aucun outil execute alors que la mission en attendait : "
                "reussite non prouvee.",
                mission_id,
            )

        # PATCH6_CONTRAT_RESULTATS_STRICT_V1
        if resultats_outils:
            champs_obligatoires = {
                "outil", "statut", "disponible", "autorise",
                "arguments_valides", "execute", "resultat",
                "verification",
            }
            for index, resultat_outil in enumerate(resultats_outils):
                if not isinstance(resultat_outil, dict):
                    return self._rejeter(
                        f"Resultat d'outil invalide a l'index {index} : "
                        "un dictionnaire est attendu.",
                        mission_id,
                    )

                champs_absents = champs_obligatoires - resultat_outil.keys()
                if champs_absents:
                    details = ", ".join(sorted(champs_absents))
                    return self._rejeter(
                        f"Contrat de resultat incomplet a l'index {index} : "
                        f"champs absents : {details}.",
                        mission_id,
                    )

                if not isinstance(resultat_outil.get("verification"), dict):
                    return self._rejeter(
                        f"Verification invalide pour l'outil "
                        f"'{resultat_outil.get('outil', 'inconnu')}'.",
                        mission_id,
                    )

        # PATCH5_CONTRAT_OUTILS_V1
        if resultats_outils:
            echecs = [
                r for r in resultats_outils
                if (
                    r.get("statut") in {
                        "outil_inconnu",
                        "non_autorise",
                        "arguments_invalides",
                        "echec_execution",
                    }
                    or r.get("execute") is False
                )
            ]

            # Compatibilite prudente avec les anciens resultats.
            if not echecs:
                echecs = [
                    r for r in resultats_outils
                    if (
                        str(r.get("resultat", ""))
                        .strip()
                        .lower()
                        .startswith("erreur")
                        and "statut" not in r
                    )
                ]

            if echecs:
                details = "; ".join(
                    f"{r.get('outil', 'outil inconnu')}: "
                    f"{r.get('resultat', 'echec inconnu')}"
                    for r in echecs
                )
                return self._rejeter(
                    f"Action(s) en echec detectee(s) : {details}",
                    mission_id,
                )

        if resultats_outils:
            # PATCH6_PREUVE_SUCCES_V1
            # Une action executee n'est validee que si une preuve
            # independante affirme explicitement verifie=True.
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
                    mission_id,
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
                    mission_id,
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
        # Ajoute la categorie de cause au diagnostic de base.
        diagnostic = self._diagnostiquer_echec_base(
            validation, resultats_outils
        )
        if diagnostic.get("echec"):
            diagnostic["categorie"] = classer_erreur(
                diagnostic.get("raison")
            )
        else:
            diagnostic["categorie"] = None
        return diagnostic

    def _diagnostiquer_echec_base(self, validation, resultats_outils=None):
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
            if (
                r.get("statut") in {
                    "outil_inconnu",
                    "non_autorise",
                    "arguments_invalides",
                    "echec_execution",
                }
                or r.get("execute") is False
            )
        ]

        if not echecs_action:
            echecs_action = [
                r for r in resultats_outils
                if (
                    str(r.get("resultat", ""))
                    .strip()
                    .lower()
                    .startswith("erreur")
                    and "statut" not in r
                )
            ]

        if echecs_action:
            premier = echecs_action[0]
            outil = premier.get("outil")

            # Une erreur d'exécution n'est pas automatiquement rejouable.
            # La politique d'autorisation décide séparément si une correction
            # peut être tentée.
            return {
                "echec": True,
                "type": "action",
                "outil": outil,
                "corrigeable": outil == "ecrire_fichier",
                "raison": str(premier.get(
                    "resultat",
                    validation.get(
                        "avertissement",
                        "Une action d'outil a echoue."
                    )
                ))
            }

        echecs_verification = [
            r for r in resultats_outils
            if isinstance(r.get("verification"), dict)
            and r["verification"].get("verifie") is False
        ]

        if echecs_verification:
            premier = echecs_verification[0]
            verification = premier.get("verification", {})
            outil = premier.get("outil")

            return {
                "echec": True,
                "type": "verification",
                "outil": outil,
                "corrigeable": outil == "ecrire_fichier",
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

        if self.corrections_utilisees >= self.max_corrections:
            return {
                "autorisee": False,
                "raison": (
                    "La limite d'une correction automatique par demande "
                    "a deja ete atteinte."
                )
            }

        self.corrections_utilisees += 1

        self.logger.enregistrer(
            f"[Validation] Correction automatique autorisee pour '{outil}'. "
            f"Utilisation {self.corrections_utilisees}/{self.max_corrections}."
        )

        return {
            "autorisee": True,
            "raison": (
                f"L'outil '{outil}' est autorise a etre rejoue une seule fois "
                "par demande."
            )
        }

    def _rejeter(self, raison, mission_id=None):
        self.logger.enregistrer(
            f"[Validation] Resultat rejete : {raison}"
            + (f" (mission {mission_id})" if mission_id else "")
        )
        return {"valide": False, "avertissement": raison}
