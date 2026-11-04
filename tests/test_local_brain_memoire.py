from core.local_brain import LocalBrain

FAUSSE = {
    "projets": ["Le projet Sam Sarr utilise Python", "Projet Hale-Bou-Rer"],
    "preferences": [],
}


def cerveau(monkeypatch, memoire=FAUSSE):
    monkeypatch.setattr(LocalBrain, "_lire_memoire", lambda self: memoire)
    return LocalBrain()


class TestListesMemoire:
    def test_liste_des_projets(self, monkeypatch):
        r = cerveau(monkeypatch).repondre("Quels sont mes projets ?")
        assert "Voice Music" in r
        assert "Mon-Jarvis-ia" in r
        assert "Hale-Bou-Rer" in r
        assert "Tabac Mauritanie Express" in r
        assert "Application mobile de fitness" not in r
        assert "Application Salon de Coiffure" not in r

    def test_liste_vide(self, monkeypatch):
        r = cerveau(monkeypatch).repondre("mes préférences")
        assert "rien enregistré" in r

    def test_question_precise_va_vers_ia(self, monkeypatch):
        assert cerveau(monkeypatch).repondre("Que sais-tu de mon projet Hale-Bou-Rer ?") is None

    def test_heure_reste_locale(self, monkeypatch):
        assert cerveau(monkeypatch).repondre("quelle heure est-il").startswith("Il est ")
