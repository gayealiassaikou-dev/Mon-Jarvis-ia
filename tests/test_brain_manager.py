from core.brain_manager import BrainManager


def test_charge_les_documents_officiels_de_sam_sarr():
    brain = BrainManager()

    assert "partenaire/brain/identity" in brain.connaissances
    assert "partenaire/brain/mission" in brain.connaissances


def test_recherche_le_nom_de_sam_sarr():
    brain = BrainManager()

    resultats = brain.rechercher_connaissances("Sam Sarr", limite=5)

    assert resultats
    assert any("partenaire/brain/" in resultat["nom"] for resultat in resultats)



def test_classe_les_documents_par_pertinence():
    brain = BrainManager()
    brain.connaissances = {
        "guide_general": "Le fournisseur est configuré dans le projet.",
        "routeur_ia": (
            "Le routeur choisit le fournisseur. "
            "Le routeur gere le choix du fournisseur."
        ),
    }

    resultats = brain.rechercher_connaissances(
        "routeur fournisseur", limite=2
    )

    assert resultats[0]["nom"] == "routeur_ia"
    assert resultats[0]["score"] > resultats[1]["score"]


def test_recherche_insensible_aux_accents():
    brain = BrainManager()
    brain.connaissances = {
        "securite": "La sécurité protège les fichiers."
    }

    resultats = brain.rechercher_connaissances("securite")

    assert resultats
    assert resultats[0]["nom"] == "securite"
