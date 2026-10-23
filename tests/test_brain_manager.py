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
