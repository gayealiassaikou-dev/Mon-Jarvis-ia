from voice_manager import VoiceManager

voice = VoiceManager()

print("=== Test VoiceManager ===")

texte = voice.ecouter_et_transcrire()

print("Transcription :", texte)
