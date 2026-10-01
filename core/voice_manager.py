import os
import subprocess
import time
import wave
import struct
import requests
from dotenv import load_dotenv

load_dotenv()

FICHIER_AUDIO_TEMP = "audio_temp.wav"
FICHIER_AUDIO_CONVERTI = "audio_temp_converti.wav"


class VoiceManager:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.url_transcription = "https://api.groq.com/openai/v1/audio/transcriptions"
        self.vitesse_voix = 1.0

    def _nettoyer_texte(self, texte):
        import re
        texte = texte.replace("[Secours Gemini]", "")
        texte = re.sub(r"\*\*|\*|#{1,6}\s*|_{1,2}|`", "", texte)
        texte = re.sub(r"^-{2,}$", "", texte, flags=re.MULTILINE)
        texte = re.sub(r"^\s*-\s+", "", texte, flags=re.MULTILINE)
        return texte.strip()

    MAX_MOTS_VOCAL = 40

    def _limiter_longueur(self, texte):
        import re
        lignes = [l for l in texte.splitlines() if "|" not in l and "<br>" not in l]
        texte = " ".join(lignes)
        phrases = re.split(r"(?<=[.!?])\s+", texte.strip())
        retenues = []
        total = 0
        for phrase in phrases:
            nb = len(phrase.split())
            if retenues and total + nb > self.MAX_MOTS_VOCAL:
                break
            retenues.append(phrase)
            total += nb
        court = " ".join(retenues)
        mots = court.split()
        if len(mots) > 60:
            court = " ".join(mots[:60])
        if len(retenues) < len(phrases):
            court += " Le reste est affiché à l'écran."
        return court

    def definir_vitesse(self, vitesse):
        vitesse = float(vitesse)
        vitesse = max(0.5, min(2.0, vitesse))
        self.vitesse_voix = vitesse
        print(f"[🎚️ Vitesse vocale : {self.vitesse_voix:.1f}x]")
        return self.vitesse_voix

    def _moteur_android_dispo(self):
        try:
            r = subprocess.run(
                ["termux-tts-engines"],
                capture_output=True, text=True, timeout=8
            )
            return len(r.stdout.strip()) > 2
        except Exception:
            return False

    def _duree_audio(self, fichier, texte):
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", fichier],
                capture_output=True, text=True, timeout=10
            )
            return float(r.stdout.strip())
        except Exception:
            return max(2.0, len(texte.split()) * 0.45)

    def _jouer_fichier(self, fichier, duree):
        subprocess.run(
            ["termux-media-player", "play", fichier],
            check=False, timeout=10
        )
        time.sleep(duree + 1)
        subprocess.run(
            ["termux-media-player", "stop"],
            check=False, timeout=10
        )

    def _parler_gtts(self, texte):
        fichier = "voix_gtts.mp3"
        try:
            from gtts import gTTS
            gTTS(texte, lang="fr").save(fichier)
            duree = self._duree_audio(fichier, texte)
            print("[🔊 Voix gTTS.]")
            self._jouer_fichier(fichier, duree)
            return True
        except Exception as e:
            print(f"[gTTS indisponible : {e}]")
            return False
        finally:
            if os.path.exists(fichier):
                os.remove(fichier)

    def _parler_secours(self, texte):
        if self._parler_gtts(texte):
            print("[🔊 Jarvis a terminé la commande vocale.]")
            time.sleep(1)
            return True
        fichier = "voix_secours.wav"
        try:
            print("[🔊 Voix de secours (espeak).]")
            subprocess.run(
                ["espeak", "-v", "fr", "-s", str(int(150 * self.vitesse_voix)),
                 "-w", fichier, texte],
                check=False, timeout=30
            )
            if not os.path.exists(fichier):
                print("[Voix de secours indisponible, réponse en texte seulement.]")
                return False
            with wave.open(fichier, "rb") as w:
                duree = w.getnframes() / float(w.getframerate())
            self._jouer_fichier(fichier, duree)
            os.remove(fichier)
            print("[🔊 Jarvis a terminé la commande vocale.]")
            time.sleep(1)
            return True
        except Exception as e:
            print(f"Erreur voix de secours : {e}")
            return False

    def parler(self, texte):
        try:
            texte_propre = self._nettoyer_texte(texte)
            texte_propre = self._limiter_longueur(texte_propre)

            if not texte_propre:
                return True

            print("[🔊 Jarvis parle...]")
            if not self._moteur_android_dispo():
                return self._parler_secours(texte_propre)

            # Google TTS
            # termux-tts-speak doit terminer son traitement avant
            # que cette fonction rende la main à Jarvis.
            subprocess.run(
                [
                    "termux-tts-speak",
                    "-l", "fr",
                    "-r", str(self.vitesse_voix),
                    "-s", "MUSIC",
                    texte_propre
                ],
                check=False,
                timeout=60
            )

            print("[🔊 Jarvis a terminé la commande vocale.]")
            time.sleep(1)
            return True

        except Exception as e:
            print(f"Erreur synthese vocale : {e}")
            return False

    VOLUME_MIN_VOIX = 300

    def _mesurer_volume(self, chemin_fichier):
        fichier_converti = chemin_fichier + "_conv.wav"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", chemin_fichier, "-ar", "16000", "-ac", "1", fichier_converti],
                capture_output=True, timeout=15
            )

            if not os.path.exists(fichier_converti):
                return 0

            with wave.open(fichier_converti, "rb") as wf:
                nb_frames = wf.getnframes()
                if nb_frames == 0:
                    return 0
                donnees = wf.readframes(nb_frames)
                echantillons = struct.unpack(f"<{len(donnees)//2}h", donnees)
                if not echantillons:
                    return 0
                somme_carres = sum(s * s for s in echantillons)
                rms = (somme_carres / len(echantillons)) ** 0.5
                return rms
        except Exception as e:
            print(f"Erreur mesure volume : {e}")
            return 0
        finally:
            if os.path.exists(fichier_converti):
                os.remove(fichier_converti)

    def _arreter_micro(self):
        try:
            subprocess.run(
                ["termux-microphone-record", "-q"],
                timeout=8,
                capture_output=True
            )
        except subprocess.TimeoutExpired:
            print("[VOICE] Arret du micro lent, on continue.")
        except Exception:
            pass
        time.sleep(0.5)

    def enregistrer(self, duree_secondes=5):
        try:
            self._arreter_micro()

            if os.path.exists(FICHIER_AUDIO_TEMP):
                os.remove(FICHIER_AUDIO_TEMP)

            subprocess.run(
                ["termux-microphone-record", "-f", FICHIER_AUDIO_TEMP,
                 "-l", str(duree_secondes)],
                timeout=15
            )

            time.sleep(duree_secondes + 2)

            self._arreter_micro()

            if (not os.path.exists(FICHIER_AUDIO_TEMP)
                    or os.path.getsize(FICHIER_AUDIO_TEMP) < 1000):
                return False

            return True

        except Exception as e:
            print(f"Erreur enregistrement : {e}")
            return False

    PHRASES_HALLUCINATION = [
        "sous-titrage", "sous-titre", "société radio-canada", "radio-canada",
        "amara.org", "merci d'avoir regarde", "merci d'avoir regardé",
        "abonnez-vous", "n'hesitez pas a vous abonner"
    ]

    def _est_hallucination(self, texte):
        texte_lower = texte.strip().lower()
        if len(texte_lower) < 3:
            return True
        for phrase in self.PHRASES_HALLUCINATION:
            if phrase in texte_lower:
                return True
        return False

    def _transcrire_assemblyai(self, fichier_audio):
        """Transcription rapide via AssemblyAI."""
        import json

        api_key = os.getenv("ASSEMBLYAI_API_KEY")

        if not api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY absente")

        headers = {
            "authorization": api_key
        }

        print("[VOICE] AssemblyAI : envoi audio...")

        with open(fichier_audio, "rb") as f:
            upload = requests.post(
                "https://api.assemblyai.com/v2/upload",
                headers=headers,
                data=f,
                timeout=30
            )

        if upload.status_code != 200:
            raise RuntimeError(
                f"Upload AssemblyAI HTTP {upload.status_code}: "
                f"{upload.text[:300]}"
            )

        upload_url = upload.json().get("upload_url")

        if not upload_url:
            raise RuntimeError("AssemblyAI : upload_url absent")

        demande = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={
                **headers,
                "content-type": "application/json"
            },
            json={
                "audio_url": upload_url,
                "language_code": "fr",
                "word_boost": ["Jarvis", "Assistant", "mode texte", "reviens en texte"],
                "boost_param": "high"
            },
            timeout=30
        )

        if demande.status_code not in (200, 201):
            raise RuntimeError(
                f"Transcription AssemblyAI HTTP {demande.status_code}: "
                f"{demande.text[:300]}"
            )

        transcript_id = demande.json().get("id")

        if not transcript_id:
            raise RuntimeError("AssemblyAI : ID transcription absent")

        print("[VOICE] AssemblyAI : transcription en cours...")

        url_resultat = (
            "https://api.assemblyai.com/v2/transcript/"
            + transcript_id
        )

        debut = time.time()

        while time.time() - debut < 30:
            resultat = requests.get(
                url_resultat,
                headers=headers,
                timeout=15
            )

            if resultat.status_code != 200:
                raise RuntimeError(
                    f"Résultat AssemblyAI HTTP {resultat.status_code}: "
                    f"{resultat.text[:300]}"
                )

            donnees = resultat.json()
            statut = donnees.get("status")

            if statut == "completed":
                texte = (donnees.get("text") or "").strip()

                if not texte:
                    raise RuntimeError(
                        "AssemblyAI : transcription vide"
                    )

                print("[VOICE] AssemblyAI : transcription réussie.")
                return texte

            if statut == "error":
                raise RuntimeError(
                    "AssemblyAI : "
                    + str(donnees.get("error", "erreur inconnue"))
                )

            time.sleep(0.5)

        raise TimeoutError(
            "AssemblyAI : délai de transcription dépassé"
        )

    def transcrire(self):
        if not os.path.exists(FICHIER_AUDIO_TEMP):
            return "Erreur : aucun fichier audio a transcrire."

        # Android/Termux peut créer un conteneur MP4/AAC
        # malgré l'extension .wav.
        # Conversion en véritable WAV PCM 16 kHz mono.
        try:
            if os.path.exists(FICHIER_AUDIO_CONVERTI):
                os.remove(FICHIER_AUDIO_CONVERTI)

            resultat_ffmpeg = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", FICHIER_AUDIO_TEMP,
                    "-vn",
                    "-ac", "1",
                    "-ar", "16000",
                    "-c:a", "pcm_s16le",
                    FICHIER_AUDIO_CONVERTI
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if (
                resultat_ffmpeg.returncode != 0
                or not os.path.exists(FICHIER_AUDIO_CONVERTI)
            ):
                erreur = resultat_ffmpeg.stderr[-1000:]
                return f"Erreur conversion audio FFmpeg : {erreur}"

            print("[VOICE] Conversion audio réussie : WAV PCM 16 kHz mono")

        except FileNotFoundError:
            return "Erreur : FFmpeg est introuvable."

        except subprocess.TimeoutExpired:
            return "Erreur : conversion FFmpeg trop longue."

        except Exception as e:
            return f"Erreur conversion audio : {e}"

        if os.getenv("ASSEMBLYAI_API_KEY"):
            try:
                texte_aai = self._transcrire_assemblyai(FICHIER_AUDIO_CONVERTI)
                if texte_aai and not self._est_hallucination(texte_aai):
                    for f in (FICHIER_AUDIO_TEMP, FICHIER_AUDIO_CONVERTI):
                        if os.path.exists(f):
                            os.remove(f)
                    return texte_aai
            except Exception as e:
                print(f"[VOICE] AssemblyAI a échoué : {e}")
                if "transcription vide" in str(e):
                    for f in (FICHIER_AUDIO_TEMP, FICHIER_AUDIO_CONVERTI):
                        if os.path.exists(f):
                            os.remove(f)
                    return "Erreur : aucune parole detectee."

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            return "Erreur : GEMINI_API_KEY absente du fichier .env."

        try:
            import base64

            with open(FICHIER_AUDIO_CONVERTI, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode("utf-8")

            data = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "Transcris exactement ce que dit la personne "
                                    "dans cet enregistrement. "
                                    "Réponds uniquement avec la transcription "
                                    "en français, sans commentaire."
                                )
                            },
                            {
                                "inline_data": {
                                    "mime_type": "audio/wav",
                                    "data": audio_base64
                                }
                            }
                        ]
                    }
                ]
            }

            url = (
                "https://generativelanguage.googleapis.com/"
                "v1beta/models/gemini-flash-latest:generateContent"
            )

            # Appel Gemini avec plusieurs tentatives
            # en cas de surcharge temporaire.
            resultat = None
            derniere_erreur = None

            for tentative in range(1, 4):
                try:
                    print(
                        f"[VOICE] Tentative Gemini "
                        f"{tentative}/3..."
                    )

                    r = requests.post(
                        url,
                        headers={"x-goog-api-key": api_key},
                        json=data,
                        timeout=60
                    )

                    if r.ok:
                        resultat = r.json()
                        print("[VOICE] Réponse Gemini reçue.")
                        break

                    try:
                        details = r.json()
                        message = details.get(
                            "error", {}
                        ).get(
                            "message",
                            r.text
                        )
                    except Exception:
                        message = r.text

                    derniere_erreur = message
                    message_min = message.lower()

                    temporaire = (
                        r.status_code in (
                            429, 500, 502, 503, 504
                        )
                        or "high demand" in message_min
                        or "temporarily" in message_min
                        or "unavailable" in message_min
                        or "overloaded" in message_min
                    )

                    if not temporaire:
                        return (
                            "Erreur transcription Gemini : "
                            f"{message}"
                        )

                    if tentative < 3:
                        attente = tentative * 3

                        print(
                            "[VOICE] Gemini temporairement "
                            "indisponible."
                        )

                        print(
                            f"[VOICE] Nouvel essai dans "
                            f"{attente} secondes..."
                        )

                        time.sleep(attente)

                except requests.exceptions.Timeout as e:
                    derniere_erreur = str(e)

                    if tentative < 3:
                        attente = tentative * 3

                        print(
                            "[VOICE] Timeout Gemini."
                        )

                        print(
                            f"[VOICE] Nouvel essai dans "
                            f"{attente} secondes..."
                        )

                        time.sleep(attente)

                except requests.exceptions.RequestException as e:
                    derniere_erreur = str(e)

                    if tentative < 3:
                        attente = tentative * 3

                        print(
                            "[VOICE] Erreur réseau Gemini."
                        )

                        print(
                            f"[VOICE] Nouvel essai dans "
                            f"{attente} secondes..."
                        )

                        time.sleep(attente)

            if resultat is None:
                return (
                    "Erreur transcription Gemini après "
                    "3 tentatives : "
                    f"{derniere_erreur}"
                )

            texte = (
                resultat
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )

            if self._est_hallucination(texte):
                return "Erreur : aucune parole detectee."

            return texte

        except requests.exceptions.HTTPError as e:
            try:
                details = e.response.json()
                message = details.get("error", {}).get("message", str(e))
            except Exception:
                message = str(e)

            return f"Erreur transcription Gemini : {message}"

        except Exception as e:
            return f"Erreur transcription Gemini : {e}"

        finally:
            if os.path.exists(FICHIER_AUDIO_TEMP):
                os.remove(FICHIER_AUDIO_TEMP)

            if os.path.exists(FICHIER_AUDIO_CONVERTI):
                os.remove(FICHIER_AUDIO_CONVERTI)

    def ecouter_et_transcrire(self, duree_secondes=5):
        if not self.enregistrer(duree_secondes):
            return "Erreur : impossible d'enregistrer l'audio."

        return self.transcrire()
