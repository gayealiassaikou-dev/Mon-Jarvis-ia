from core.memory_manager import MemoryManager


def creer(memoire):
    gestionnaire = MemoryManager.__new__(MemoryManager)
    gestionnaire.memoire = memoire
    return gestionnaire


class TestRecherchePertinente:
    def test_accents(self):
        m = creer({"preferences": ["Préférer les commandes courtes et progressives"]})
        resultats = m.rechercher_souvenirs_pertinents("preferer commandes")
        assert len(resultats) == 1
        assert resultats[0].startswith("[preferences] ")

    def test_classement_par_pertinence(self):
        m = creer({"projets": [
            "Le projet Halibourer utilise Flask",
            "Le projet Sam Sarr utilise Python",
        ]})
        resultats = m.rechercher_souvenirs_pertinents("projet sam python")
        assert resultats[0] == "[projets] Le projet Sam Sarr utilise Python"
        assert len(resultats) == 2

    def test_aucun_resultat(self):
        m = creer({"notes": ["Acheter du pain"]})
        assert m.rechercher_souvenirs_pertinents("photosynthese") == []

    def test_limite(self):
        m = creer({"notes": [f"Note python numero {i}" for i in range(7)]})
        assert len(m.rechercher_souvenirs_pertinents("python numero", limite=3)) == 3

    def test_ponctuation(self):
        m = creer({"connaissances": ["Le projet utilise Python."]})
        assert len(m.rechercher_souvenirs_pertinents("Python ?")) == 1

    def test_mots_vides_seuls(self):
        m = creer({"notes": ["Le projet est en cours"]})
        assert m.rechercher_souvenirs_pertinents("Quel est le") == []

    def test_limite_zero(self):
        m = creer({"notes": ["Note python"]})
        assert m.rechercher_souvenirs_pertinents("python", limite=0) == []
