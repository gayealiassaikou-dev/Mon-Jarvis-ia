from core.memory_manager import MemoryManager


def creer(memoire):
    gestionnaire = MemoryManager.__new__(MemoryManager)
    gestionnaire.memoire = memoire
    return gestionnaire


class TestRechercheCategories:
    def test_pluriel(self):
        m = creer({"connaissances": ["Le projet utilise un modele local"]})
        assert len(m.rechercher_souvenirs_pertinents("projets modeles")) == 1

    def test_categorie_nommee(self):
        m = creer({
            "preferences": ["Commandes courtes", "Reponses simples", "Toujours en francais"],
            "projets": ["Projet Sam Sarr"],
        })
        resultats = m.rechercher_souvenirs_pertinents("quelles sont mes preferences")
        assert len(resultats) == 3
        assert all(r.startswith("[preferences] ") for r in resultats)

    def test_categorie_ne_deborde_pas(self):
        m = creer({"notes": ["Acheter du pain"], "projets": ["Projet Sam Sarr"]})
        resultats = m.rechercher_souvenirs_pertinents("mes projets")
        assert len(resultats) == 1
        assert resultats[0].startswith("[projets] ")

    def test_mot_precis_prioritaire(self):
        m = creer({"preferences": ["Commandes courtes", "Je prefere Python"]})
        resultats = m.rechercher_souvenirs_pertinents("preferences python")
        assert resultats[0] == "[preferences] Je prefere Python"
