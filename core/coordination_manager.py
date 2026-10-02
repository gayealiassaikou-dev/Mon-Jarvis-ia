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

    def livrer(self, reponse, mission_id=None):
        if mission_id:
            self.logger.enregistrer(f"[Coordination] Livraison du resultat pour mission {mission_id}.")
        return reponse
