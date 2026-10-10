import inspect
import unittest

import core.voice_manager as vmod


def trouver_classe():
    for _, classe in inspect.getmembers(vmod, inspect.isclass):
        if "_normaliser_transcription" in classe.__dict__:
            return classe
    raise RuntimeError("Classe avec _normaliser_transcription introuvable")


class TestNormalisationSTT(unittest.TestCase):
    def setUp(self):
        self.vm = object.__new__(trouver_classe())

    def norm(self, texte):
        return self.vm._normaliser_transcription(texte)

    def test_texte_vide_ne_boucle_pas(self):
        self.assertEqual(self.norm(""), "")
        self.assertIsNone(self.norm(None))

    def test_variantes_samba_sarr(self):
        for entree in ("samba sar", "samba ça", "samba serre", "samba sert"):
            self.assertEqual(self.norm(entree), "Samba Sarr", entree)

    def test_majuscules_et_phrase(self):
        self.assertEqual(self.norm("SAMBA SAR"), "Samba Sarr")
        self.assertEqual(self.norm("Bonjour samba sar"), "Bonjour Samba Sarr")

    def test_phrase_sans_rapport_inchangee(self):
        self.assertEqual(self.norm("quelle heure est-il"), "quelle heure est-il")


if __name__ == "__main__":
    unittest.main()
