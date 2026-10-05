class CoordinationManager:

    def __init__(self, mission_manager, logger):
        self.mission_manager = mission_manager
        self.logger = logger

    def preparer(self, decision, commande):
        agent = decision.get("agent")
        analyse = decision.get("analyse", {})
        outils = decision.get("outils_suggeres", [])

        self.logger.enregistrer(
            f"[Coordination] Preparation - agent: {agent}, "
            f"risques: {analyse.get('risques')}, outils: {outils}"
        )

        return {
            "agent": agent,
            "analyse": analyse,
            "outils": outils
        }

    def demarrer_mission(self, mission_id):
        if not mission_id:
            return
        self.mission_manager.mettre_a_jour_statut(mission_id, "en_cours")
        self.logger.enregistrer(f"[Coordination] Mission {mission_id} demarree.")

    def superviser_resultat(self, reponse, mission_id=None, validation=None):
        erreur_detectee = False

        if not reponse or not reponse.strip():
            erreur_detectee = True
        elif reponse.startswith("Erreur IA"):
            erreur_detectee = True

        if validation is not None and not validation.get("valide", False):
            erreur_detectee = True

        if mission_id:
            if erreur_detectee:
                self.mission_manager.mettre_a_jour_statut(mission_id, "bloquee")
                self.logger.enregistrer(
                    f"[Coordination] Mission {mission_id} bloquee - validation ou erreur detectee."
                )
            else:
                self.mission_manager.mettre_a_jour_statut(mission_id, "terminee")
                self.logger.enregistrer(
                    f"[Coordination] Mission {mission_id} terminee avec succes."
                )

        return not erreur_detectee

    def decider_suite_action(self, resultats_outils, validation=None, validation_manager=None):
        """
        Détermine la suite à donner après l'exécution des outils.

        Décisions possibles :
        - continuer : aucun échec bloquant détecté
        - bloquer : une correction automatique n'est pas autorisée
        - corriger : une correction automatique est explicitement autorisée

        Cette méthode ne lance aucune action. Elle prépare uniquement
        la décision pour la future boucle autonome.
        """
        resultats_outils = resultats_outils or []

        if not resultats_outils:
            return {
                "decision": "continuer",
                "raison": "Aucun résultat d'outil à corriger."
            }

        echecs = [
            resultat for resultat in resultats_outils
            if str(resultat.get("resultat", "")).strip().lower().startswith("erreur")
            or (
                isinstance(resultat.get("verification"), dict)
                and resultat["verification"].get("verifie") is False
            )
        ]

        if not echecs:
            return {
                "decision": "continuer",
                "raison": "Les actions exécutées ne présentent aucun échec bloquant."
            }

        if validation_manager is None:
            return {
                "decision": "bloquer",
                "raison": "Échec détecté mais aucun ValidationManager disponible pour décider d'une correction."
            }

        validation = validation or {"valide": False}

        diagnostic = validation_manager.diagnostiquer_echec(
            validation,
            resultats_outils=resultats_outils
        )

        correction = validation_manager.autoriser_correction(
            diagnostic,
            resultats_outils=resultats_outils
        )

        if correction.get("autorisee", False):
            return {
                "decision": "corriger",
                "diagnostic": diagnostic,
                "correction": correction
            }

        return {
            "decision": "bloquer",
            "diagnostic": diagnostic,
            "correction": correction
        }

    def livrer(self, reponse, mission_id=None):
        if mission_id:
            self.logger.enregistrer(f"[Coordination] Livraison du resultat pour mission {mission_id}.")
        return reponse
