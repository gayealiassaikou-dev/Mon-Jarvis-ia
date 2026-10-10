from pathlib import Path
import shutil
import py_compile
import sys


FICHIER = Path("core/decision_engine.py")
SAUVEGARDE = Path("core/decision_engine.py.sauvegarde_patch4_routage")


def echec(message):
    print(f"[PATCH 4] ERREUR : {message}")
    sys.exit(1)


if not FICHIER.exists():
    echec(f"Fichier introuvable : {FICHIER}")

original = FICHIER.read_text(encoding="utf-8")


PATCH4_DEJA_APPLIQUE = all(
    marqueur in original
    for marqueur in (
        "DESCRIPTIONS_AGENTS = {",
        "OUTILS_AGENTS_SPECIALISES = {",
        "def _construire_catalogue_agents(self, liste_agents):",
        "def _decision_securisee(self, demande, raison):",
        "def _verifier_coherence_agent_outils(self, agent, outils):",
    )
)


if SAUVEGARDE.exists():
    sauvegarde_existante = SAUVEGARDE.read_text(encoding="utf-8")

    if sauvegarde_existante != original:
        if PATCH4_DEJA_APPLIQUE:
            print(
                "[PATCH 4] Patch déjà appliqué : "
                "la sauvegarde correspond à la version originale "
                "pré-Patch4. Les modifications seront ignorées."
            )
        else:
            echec(
                f"La sauvegarde existe déjà et son contenu diffère de "
                f"{FICHIER}. Refus de continuer."
            )
    else:
        print(
            f"[PATCH 4] Sauvegarde existante vérifiée : {SAUVEGARDE}"
        )
else:
    if PATCH4_DEJA_APPLIQUE:
        echec(
            "Patch 4 semble déjà appliqué mais la sauvegarde originale "
            "est absente. Refus de continuer sans possibilité de rollback."
        )

    SAUVEGARDE.write_text(original, encoding="utf-8")
    print(f"[PATCH 4] Sauvegarde créée : {SAUVEGARDE}")


ancien_catalogue = '''    def _construire_catalogue_outils(self):
        """
        Construit la description sémantique des outils disponibles.

        Seuls les outils présents dans TOUS_LES_OUTILS sont exposés.
        """

        lignes = []

        for outil in self.outils_disponibles:
            description = self.DESCRIPTIONS_OUTILS.get(
                outil,
                "Outil disponible dans le système de Jarvis."
            )

            lignes.append(
                f"- {outil} : {description}"
            )

        return "\\n".join(lignes)

    def decider(self, demande):
'''

nouveau_catalogue = '''    DESCRIPTIONS_AGENTS = {
        "00_directeur_ia": (
            "Coordonne les missions complexes, décompose les objectifs "
            "et orchestre les autres agents. À privilégier lorsqu'aucun "
            "spécialiste unique ne correspond clairement à la demande."
        ),
        "01_developpeur": (
            "Développe et corrige du code, manipule les fichiers du projet, "
            "travaille sur les applications et utilise GitHub pour les "
            "actions techniques."
        ),
        "02_designer": (
            "Conçoit les interfaces, l'UX, l'UI, les maquettes et "
            "l'identité visuelle des produits numériques."
        ),
        "03_recherche": (
            "Effectue des recherches, compare des solutions et vérifie "
            "des informations et des sources."
        ),
        "04_business": (
            "Analyse le marché, les utilisateurs, la concurrence, la "
            "monétisation, le marketing et les modèles économiques."
        ),
        "05_architecte_ia": (
            "Conçoit l'architecture logicielle et IA, les composants, "
            "les technologies et la structure globale d'un système."
        ),
        "06_memoire_ia": (
            "Gère la mémorisation, l'organisation et la récupération "
            "des informations importantes."
        ),
        "07_automatisation_ia": (
            "Conçoit et exécute des automatisations, workflows, "
            "intégrations et tâches répétitives."
        ),
        "08_testeur_ia": (
            "Teste les logiciels, détecte les bugs et vérifie la qualité "
            "et la stabilité des réalisations."
        ),
        "09_securite_ia": (
            "Analyse les risques, permissions, secrets, dépendances "
            "et problèmes de sécurité."
        ),
        "10_assistant_vocal_ia": (
            "Travaille sur la voix, la reconnaissance vocale, la synthèse "
            "vocale et les interactions vocales."
        ),
        "11_gestionnaire_outils_ia": (
            "Sélectionne les outils et ressources les plus adaptés "
            "à une mission et organise leur utilisation."
        ),
    }

    OUTILS_AGENTS_SPECIALISES = {
        "ecrire_fichier": "01_developpeur",
        "supprimer_fichier": "01_developpeur",
        "creer_dossier": "01_developpeur",
        "github_ecrire_fichier": "01_developpeur",
        "github_creer_repo": "01_developpeur",
        "rechercher_web": "03_recherche",
        "memoriser_info": "06_memoire_ia",
        "rechercher_souvenir": "06_memoire_ia",
        "creer_projet": "07_automatisation_ia",
        "ajouter_tache": "07_automatisation_ia",
        "terminer_tache": "07_automatisation_ia",
        "supprimer_tache": "07_automatisation_ia",
        "supprimer_projet": "07_automatisation_ia",
        "modifier_statut_projet": "07_automatisation_ia",
    }

    def _construire_catalogue_outils(self):
        """
        Construit la description sémantique des outils disponibles.

        Seuls les outils présents dans TOUS_LES_OUTILS sont exposés.
        """

        lignes = []

        for outil in self.outils_disponibles:
            description = self.DESCRIPTIONS_OUTILS.get(
                outil,
                "Outil disponible dans le système de Jarvis."
            )

            lignes.append(
                f"- {outil} : {description}"
            )

        return "\\n".join(lignes)

    def _construire_catalogue_agents(self, liste_agents):
        """
        Construit le catalogue des agents réellement chargés par Jarvis.

        Les profils sont fournis au moteur de décision afin que le LLM
        choisisse un spécialiste sur la base de son rôle réel et non
        uniquement sur son nom.
        """

        lignes = []

        for agent in liste_agents:
            description = self.DESCRIPTIONS_AGENTS.get(
                agent,
                "Agent spécialisé dont le rôle détaillé n'est pas défini."
            )

            lignes.append(
                f"- {agent} : {description}"
            )

        return "\\n".join(lignes)

    def _decision_securisee(self, demande, raison):
        """
        Produit une décision sans action lorsqu'une décision du LLM
        ne peut pas être considérée comme fiable.
        """

        print(
            "[DecisionEngine] Décision sécurisée : "
            f"{raison}"
        )

        return {
            "agent": "00_directeur_ia",
            "analyse": {
                "difficulte": "moyenne",
                "risques": "eleve",
                "validation_requise": True,
                "resume": demande
            },
            "outils_suggeres": [],
            "decision_securisee": True,
            "raison_decision": raison,
        }

    def _verifier_coherence_agent_outils(self, agent, outils):
        """
        Vérifie qu'un agent spécialisé n'est pas associé à un outil
        manifestement réservé à un autre domaine.

        Le Directeur IA et le Gestionnaire des Outils IA restent des
        agents d'orchestration et ne déclenchent pas cette contrainte.
        """

        if agent in {
            "00_directeur_ia",
            "11_gestionnaire_outils_ia",
        }:
            return True

        for outil in outils:
            agent_attendu = self.OUTILS_AGENTS_SPECIALISES.get(outil)

            if agent_attendu and agent != agent_attendu:
                return False

        return True

    def decider(self, demande):
'''

if not PATCH4_DEJA_APPLIQUE and original.count(ancien_catalogue) != 1:
    echec(
        "Bloc catalogue/decider introuvable exactement une fois. "
        "Aucune modification effectuée."
    )


ancien_prompt = '''            f"Agents disponibles : {', '.join(liste_agents)}.\\n\\n"

            "Outils disponibles et leurs fonctions :\\n"
            f"{catalogue_outils}\\n\\n"
'''

nouveau_prompt = '''            "Agents disponibles et responsabilités :\\n"
            f"{catalogue_agents}\\n\\n"

            "Outils disponibles et leurs fonctions :\\n"
            f"{catalogue_outils}\\n\\n"
'''

if not PATCH4_DEJA_APPLIQUE and original.count(ancien_prompt) != 1:
    echec(
        "Bloc du catalogue des agents introuvable exactement une fois. "
        "Aucune modification effectuée."
    )


ancien_regles = '''            "Sélectionne uniquement les outils réellement nécessaires "
            "à l'exécution de la demande.\\n\\n"

            "Règles importantes pour les outils :\\n"
'''

nouveau_regles = '''            "Sélectionne uniquement les outils réellement nécessaires "
            "à l'exécution de la demande.\\n\\n"

            "Règles de routage des agents :\\n"
            "- Choisis l'agent dont la responsabilité correspond le mieux "
            "à l'objectif réel de la demande.\\n"
            "- Pour du code, des bugs, des fichiers du projet ou une action "
            "GitHub technique, privilégie 01_developpeur.\\n"
            "- Pour une architecture logicielle ou IA, privilégie "
            "05_architecte_ia.\\n"
            "- Pour une recherche d'informations, privilégie 03_recherche.\\n"
            "- Pour des tests ou une vérification de qualité, privilégie "
            "08_testeur_ia.\\n"
            "- Pour la sécurité, les permissions ou les secrets, privilégie "
            "09_securite_ia.\\n"
            "- Pour la mémoire, privilégie 06_memoire_ia.\\n"
            "- Pour l'automatisation et les workflows, privilégie "
            "07_automatisation_ia.\\n"
            "- Pour le design et l'UX/UI, privilégie 02_designer.\\n"
            "- Pour le business, le marché ou la monétisation, privilégie "
            "04_business.\\n"
            "- Pour la voix, privilégie 10_assistant_vocal_ia.\\n"
            "- Pour une orchestration réellement transversale, utilise "
            "00_directeur_ia.\\n"
            "- Ne choisis jamais un agent uniquement à partir de son numéro "
            "ou de son nom.\\n\\n"

            "Règles importantes pour les outils :\\n"
'''

if not PATCH4_DEJA_APPLIQUE and original.count(ancien_regles) != 1:
    echec(
        "Bloc des règles de routage introuvable exactement une fois. "
        "Aucune modification effectuée."
    )


ancien_validation = '''            agent = data.get("agent", "00_directeur_ia")

            if agent not in liste_agents:
                agent = "00_directeur_ia"

            outils = data.get("outils_suggeres", [])
'''

nouveau_validation = '''            agent = data.get("agent")

            if not isinstance(agent, str) or not agent.strip():
                return self._decision_securisee(
                    demande,
                    "Agent absent ou vide dans la décision du LLM."
                )

            if agent not in liste_agents:
                return self._decision_securisee(
                    demande,
                    f"Agent inconnu retourné par le LLM : {agent!r}"
                )

            outils = data.get("outils_suggeres", [])
'''

if not PATCH4_DEJA_APPLIQUE and original.count(ancien_validation) != 1:
    echec(
        "Bloc de validation de l'agent introuvable exactement une fois. "
        "Aucune modification effectuée."
    )


ancien_retour = '''            # Barrière de sécurité : les outils proposés par le LLM
            # sont toujours filtrés par les permissions de l'agent.
            outils = filtrer_outils(agent, outils)

            return {
                "agent": agent,
                "analyse": {
'''

nouveau_retour = '''            # Barrière de sécurité : les outils proposés par le LLM
            # sont toujours filtrés par les permissions de l'agent.
            outils = filtrer_outils(agent, outils)

            if not self._verifier_coherence_agent_outils(agent, outils):
                return self._decision_securisee(
                    demande,
                    "Incohérence détectée entre l'agent choisi et les outils."
                )

            return {
                "agent": agent,
                "analyse": {
'''

if not PATCH4_DEJA_APPLIQUE and original.count(ancien_retour) != 1:
    echec(
        "Bloc de filtrage/retour introuvable exactement une fois. "
        "Aucune modification effectuée."
    )


ancien_catalogue_appel = '''        catalogue_outils = self._construire_catalogue_outils()

        prompt = (
'''

nouveau_catalogue_appel = '''        catalogue_outils = self._construire_catalogue_outils()
        catalogue_agents = self._construire_catalogue_agents(liste_agents)

        prompt = (
'''

if not PATCH4_DEJA_APPLIQUE and original.count(ancien_catalogue_appel) != 1:
    echec(
        "Bloc d'appel des catalogues introuvable exactement une fois. "
        "Aucune modification effectuée."
    )


# Application des remplacements sur une copie mémoire.
#
# Si Patch 4 est déjà présent, aucune réécriture du fichier source
# n'est effectuée. Le script passe directement aux tests.
if PATCH4_DEJA_APPLIQUE:
    print(
        "[PATCH 4] Version déjà appliquée détectée."
    )
    print(
        "[PATCH 4] Aucun remplacement ni écrasement de "
        "core/decision_engine.py."
    )
else:
    modifie = original
    modifie = modifie.replace(
        ancien_catalogue,
        nouveau_catalogue,
        1
    )
    modifie = modifie.replace(
        ancien_prompt,
        nouveau_prompt,
        1
    )
    modifie = modifie.replace(
        ancien_regles,
        nouveau_regles,
        1
    )
    modifie = modifie.replace(
        ancien_validation,
        nouveau_validation,
        1
    )
    modifie = modifie.replace(
        ancien_retour,
        nouveau_retour,
        1
    )
    modifie = modifie.replace(
        ancien_catalogue_appel,
        nouveau_catalogue_appel,
        1
    )

    if modifie == original:
        echec("Le contenu final n'a pas changé.")

    # Sauvegarde avant écriture.
    shutil.copy2(FICHIER, SAUVEGARDE)

try:
    if not PATCH4_DEJA_APPLIQUE:
        FICHIER.write_text(modifie, encoding="utf-8")
        print("[PATCH 4] Fichier modifié.")

    # Vérification syntaxique.
    py_compile.compile(
        str(FICHIER),
        doraise=True
    )

    print("[PATCH 4] Compilation Python : OK.")

    # Tests comportementaux avec composants factices.
    sys.path.insert(0, str(FICHIER.parent.resolve()))

    from decision_engine import DecisionEngine

    class FauxAgentManager:
        def __init__(self):
            self.agents = {
                "00_directeur_ia": "directeur",
                "01_developpeur": "developpeur",
                "02_designer": "designer",
                "03_recherche": "recherche",
                "04_business": "business",
                "05_architecte_ia": "architecte",
                "06_memoire_ia": "memoire",
                "07_automatisation_ia": "automatisation",
                "08_testeur_ia": "testeur",
                "09_securite_ia": "securite",
                "10_assistant_vocal_ia": "vocal",
                "11_gestionnaire_outils_ia": "outils",
            }

    class FauxAIEngine:
        def __init__(self, reponse):
            self.reponse = reponse

        def demander(
            self,
            prompt,
            outils_autorises=None,
            mode_action=False
        ):
            return self.reponse

    def creer_engine(reponse):
        return DecisionEngine(
            None,
            FauxAgentManager(),
            FauxAIEngine(reponse)
        )

    # Test 1 : développeur + outil fichier.
    moteur = creer_engine(
        '{"agent":"01_developpeur",'
        '"difficulte":"moyenne",'
        '"risques":"faible",'
        '"validation_requise":true,'
        '"resume":"modifier un fichier",'
        '"outils_suggeres":["ecrire_fichier"]}'
    )

    resultat = moteur.decider("Modifie un fichier du projet.")

    assert resultat["agent"] == "01_developpeur"
    assert resultat["outils_suggeres"] == ["ecrire_fichier"]

    print("[TEST 1] Développeur + fichier : OK.")

    # Test 2 : recherche.
    moteur = creer_engine(
        '{"agent":"03_recherche",'
        '"difficulte":"faible",'
        '"risques":"aucun",'
        '"validation_requise":false,'
        '"resume":"faire une recherche",'
        '"outils_suggeres":["rechercher_web"]}'
    )

    resultat = moteur.decider("Recherche une information sur le Web.")

    assert resultat["agent"] == "03_recherche"
    assert resultat["outils_suggeres"] == ["rechercher_web"]

    print("[TEST 2] Recherche : OK.")

    # Test 3 : agent inconnu = sécurité, aucun outil d'action.
    moteur = creer_engine(
        '{"agent":"99_agent_invente",'
        '"difficulte":"moyenne",'
        '"risques":"faible",'
        '"validation_requise":false,'
        '"resume":"test",'
        '"outils_suggeres":["ecrire_fichier"]}'
    )

    resultat = moteur.decider("Test agent inconnu.")

    assert resultat["decision_securisee"] is True
    assert resultat["agent"] == "00_directeur_ia"
    assert resultat["outils_suggeres"] == []
    assert resultat["analyse"]["validation_requise"] is True

    print("[TEST 3] Agent inconnu bloqué : OK.")

    # Test 4 : agent absent.
    moteur = creer_engine(
        '{"difficulte":"moyenne",'
        '"risques":"faible",'
        '"validation_requise":false,'
        '"resume":"test",'
        '"outils_suggeres":[]}'
    )

    resultat = moteur.decider("Test agent absent.")

    assert resultat["decision_securisee"] is True
    assert resultat["outils_suggeres"] == []

    print("[TEST 4] Agent absent bloqué : OK.")

    # Test 5 : incohérence agent/outils.
    moteur = creer_engine(
        '{"agent":"06_memoire_ia",'
        '"difficulte":"faible",'
        '"risques":"faible",'
        '"validation_requise":false,'
        '"resume":"test",'
        '"outils_suggeres":["ecrire_fichier"]}'
    )

    resultat = moteur.decider("Test incohérence agent outil.")

    assert resultat["decision_securisee"] is True
    assert resultat["outils_suggeres"] == []

    print("[TEST 5] Incohérence agent/outils bloquée : OK.")

    print("[PATCH 4] Tous les tests comportementaux : OK.")

except Exception as erreur:
    print(
        "[PATCH 4] ÉCHEC. Restauration de la version originale..."
    )

    shutil.copy2(SAUVEGARDE, FICHIER)

    try:
        py_compile.compile(
            str(FICHIER),
            doraise=True
        )
    except Exception as restauration_erreur:
        print(
            "[PATCH 4] ERREUR CRITIQUE : "
            "la restauration n'est pas compilable : "
            f"{restauration_erreur}"
        )
        sys.exit(2)

    print("[PATCH 4] Version originale restaurée.")
    print(f"[PATCH 4] Sauvegarde disponible : {SAUVEGARDE}")
    raise


print()
print("==========================================")
print("PATCH 4 — ROUTAGE DES AGENTS : OK")
print("==========================================")
print(f"Fichier modifié : {FICHIER}")
print(f"Sauvegarde      : {SAUVEGARDE}")
print()
print("Rollback manuel :")
print(f"cp {SAUVEGARDE} {FICHIER}")
print("==========================================")
