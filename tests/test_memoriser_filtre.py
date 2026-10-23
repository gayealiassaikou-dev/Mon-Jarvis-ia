from core.memory_manager import MemoryManager


def creer():
    m = MemoryManager.__new__(MemoryManager)
    m.memoire = {c: [] for c in ("projets", "decisions", "preferences", "connaissances", "erreurs")}
    m.sauvegarder = lambda: None
    return m


class TestFiltreMemoriser:
    def test_refuse_phrase_ia(self):
        m = creer()
        r = m.memoriser("projets", "Je peux aider a creer des projets")
        assert r.startswith("Information ignoree")
        assert m.memoire["projets"] == []

    def test_accepte_fait_utile(self):
        m = creer()
        r = m.memoriser("projets", "Le projet principal utilise Python")
        assert "memorisee" in r
        assert len(m.memoire["projets"]) == 1

    def test_doublon_avec_accents(self):
        m = creer()
        m.memoriser("preferences", "Préférer les réponses courtes")
        r = m.memoriser("preferences", "preferer les reponses courtes")
        assert "deja presente" in r
        assert len(m.memoire["preferences"]) == 1

    def test_refuse_artefact_transcription(self):
        m = creer()
        r = m.memoriser("connaissances", "Sous-titrage Société Radio-Canada")
        assert r.startswith("Information ignoree")
