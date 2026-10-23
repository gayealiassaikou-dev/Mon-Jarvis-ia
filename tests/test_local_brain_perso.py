from core.local_brain import LocalBrain


class TestQuestionsPersonnelles:
    def test_question_projet_va_vers_ia(self):
        assert LocalBrain().repondre("Que sais-tu de mon projet Hale-Bou-Rer ?") is None

    def test_question_preferences_va_vers_ia(self):
        assert LocalBrain().repondre("Que sais-tu de mes préférences de travail ?") is None

    def test_heure_reste_locale(self):
        assert LocalBrain().repondre("quelle heure est-il").startswith("Il est ")
