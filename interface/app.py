import sys
import os
import secrets
import tempfile
import queue
import threading
import json as _json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "core"))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from io import BytesIO
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from jarvis import Jarvis
from voice_manager import VoiceManager
from activity_tracker import ActivityTracker
from interface.conversation_store import ConversationStore

app = Flask(__name__)

jarvis = Jarvis()
voice = VoiceManager()
activity_tracker = ActivityTracker()
conversation_store = ConversationStore()

@app.route("/")
def accueil():
    return render_template("index.html")

@app.route("/sw.js")
def service_worker():
    response = send_from_directory(
        app.static_folder,
        "sw.js",
        mimetype="application/javascript"
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route("/health")
def health():
    return "ok", 200


@app.route("/api/audio/synthetiser", methods=["POST"])
def synthetiser_audio():
    data = request.get_json(silent=True) or {}
    texte = data.get("texte")

    if not isinstance(texte, str) or not texte.strip():
        return jsonify({"erreur": "Texte vide."}), 400

    try:
        audio = voice.generer_audio_gtts(texte)
        return send_file(
            audio,
            mimetype="audio/mpeg",
            download_name="sam-sarr.mp3"
        )
    except Exception:
        app.logger.exception("Erreur de synthèse gTTS")
        return jsonify({"erreur": "Synthèse vocale indisponible."}), 500


@app.route("/api/audio/transcrire", methods=["POST"])
def transcrire_audio_android():
    audio = request.files.get("audio")

    if audio is None:
        return jsonify({"erreur": "Fichier audio manquant."}), 400

    extension = os.path.splitext(audio.filename or "")[1].lower()
    extensions_autorisees = {
        ".m4a", ".mp4", ".wav", ".webm",
        ".ogg", ".aac", ".mp3"
    }

    if extension not in extensions_autorisees:
        return jsonify({"erreur": "Format audio non accepté."}), 400

    chemin_temporaire = None

    try:
        contenu = audio.read(25 * 1024 * 1024 + 1)

        if not contenu:
            return jsonify({"erreur": "Fichier audio vide."}), 400

        if len(contenu) > 25 * 1024 * 1024:
            return jsonify({"erreur": "Fichier audio trop volumineux."}), 413

        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=extension,
            delete=False
        ) as fichier:
            fichier.write(contenu)
            chemin_temporaire = fichier.name

        texte = voice._transcrire_assemblyai(chemin_temporaire)
        texte = voice._normaliser_transcription(texte)

        if voice._est_hallucination(texte):
            return jsonify({"erreur": "Transcription non exploitable."}), 422

        return jsonify({"message": texte})

    except Exception:
        app.logger.exception("Erreur de transcription audio Android")
        return jsonify({"erreur": "Transcription audio indisponible."}), 502

    finally:
        if chemin_temporaire and os.path.exists(chemin_temporaire):
            os.remove(chemin_temporaire)


@app.route("/activite/demarrer", methods=["POST"])
def demarrer_activite():
    demande_id = secrets.token_urlsafe(24)
    activity_tracker.demarrer(demande_id)
    return jsonify({"demande_id": demande_id})


@app.route("/activite/<demande_id>", methods=["GET"])
def consulter_activite(demande_id):
    activite = activity_tracker.consulter(demande_id)
    if activite is None:
        return jsonify({"erreur": "Activité introuvable."}), 404
    return jsonify(activite)

def _demande_musique(message):
    """Detecte 'joue ...' : renvoie (titre, lien YouTube) ou None."""
    import re, urllib.parse
    motif = r"^(?:joue(?: moi)?(?: la musique| la chanson| le morceau)?|(?:mets|lance)(?: moi)? (?:la musique|la chanson|le morceau)) (.+)$"
    m = re.match(motif, message.strip().lower().rstrip(" ?!.,;:"))
    if not m:
        return None
    titre = m.group(1).strip()
    ident = None
    try:
        import yt_dlp
        options = {"quiet": True, "no_warnings": True, "extract_flat": True,
                   "skip_download": True, "socket_timeout": 10}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info("ytsearch1:" + titre, download=False)
        entrees = (info or {}).get("entries") or []
        if entrees:
            ident = entrees[0].get("id")
    except Exception:
        ident = None
    if ident:
        return titre, "https://www.youtube.com/watch?v=" + ident + "&autoplay=1"
    return titre, "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(titre)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"reponse": "Message vide."}), 400

    demande_id = data.get("demande_id")
    if demande_id is None:
        demande_id = secrets.token_urlsafe(24)
        activity_tracker.demarrer(demande_id)
    else:
        if not isinstance(demande_id, str):
            return jsonify({"reponse": "Identifiant de suivi invalide."}), 400
        activite = activity_tracker.consulter(demande_id)
        if activite is None:
            return jsonify({"reponse": "Identifiant de suivi invalide."}), 400
        if activite["etat"] != "en_cours":
            return jsonify({"reponse": "Cette demande est déjà terminée."}), 409

    conversation_id = data.get("conversation_id")

    try:
        if conversation_id is None:
            conversation = conversation_store.creer_conversation(message)
            conversation_id = conversation["id"]
        elif (
            not isinstance(conversation_id, str)
            or conversation_store.obtenir_conversation(conversation_id) is None
        ):
            return jsonify({"reponse": "Conversation introuvable."}), 404

        conversation_store.ajouter_message(
            conversation_id, "user", message
        )
    except Exception:
        app.logger.exception("Erreur lors de la sauvegarde de la conversation")
        return jsonify({"reponse": "Impossible de sauvegarder la conversation."}), 500

    succes = False
    ouvrir_url = None
    try:
        musique = _demande_musique(message)
        if musique:
            titre_musique, ouvrir_url = musique
            reponse = "Je lance : " + titre_musique + "."
        else:
            reponse = jarvis.traiter_commande(
                message,
                retourner_reponse=True,
                activity_tracker=activity_tracker,
                demande_id=demande_id,
            )
        activity_tracker.ajouter_etape(
            demande_id, "Réponse préparée", "succes"
        )
        succes = True
    except Exception:
        app.logger.exception("Erreur dans /chat")
        reponse = "Une erreur interne est survenue. Réessaie."
    finally:
        activity_tracker.terminer(demande_id, succes=succes)

    try:
        conversation_store.ajouter_message(
            conversation_id, "assistant", str(reponse)
        )
    except Exception:
        app.logger.exception("Erreur lors de la sauvegarde de la réponse")

    return jsonify({
        "reponse": str(reponse),
        "demande_id": demande_id,
        "conversation_id": conversation_id,
        "ouvrir_url": ouvrir_url,
    })


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    """Version SSE de /chat qui stream les etapes en temps reel."""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"erreur": "Message vide."}), 400

    demande_id = secrets.token_urlsafe(24)
    activity_tracker.demarrer(demande_id)

    conversation_id = data.get("conversation_id")
    try:
        if conversation_id is None:
            conversation = conversation_store.creer_conversation(message)
            conversation_id = conversation["id"]
        conversation_store.ajouter_message(conversation_id, "user", message)
    except Exception:
        app.logger.exception("Erreur sauvegarde conversation")
        return jsonify({"erreur": "Impossible de sauvegarder."}), 500

    q = queue.Queue()
    resultat_final = {"reponse": "", "ouvrir_url": None, "succes": False}

    def _executer():
        try:
            musique = _demande_musique(message)
            if musique:
                titre, ouvrir_url = musique
                resultat_final["reponse"] = "Je lance : " + titre + "."
                resultat_final["ouvrir_url"] = ouvrir_url
            else:
                # Callback qui pousse les chunks LLM dans la queue
                def _on_chunk(texte_chunk):
                    try:
                        q.put({"type": "chunk", "texte": texte_chunk})
                    except Exception:
                        pass

                resultat_final["reponse"] = jarvis.traiter_commande(
                    message,
                    retourner_reponse=True,
                    activity_tracker=activity_tracker,
                    demande_id=demande_id,
                    on_chunk=_on_chunk,
                )
            resultat_final["succes"] = True
        except Exception as e:
            app.logger.exception("Erreur /chat/stream")
            resultat_final["reponse"] = f"Erreur interne : {e}"
        finally:
            try:
                activity_tracker.terminer(demande_id, succes=resultat_final["succes"])
            except Exception:
                pass
            q.put(None)

    thread = threading.Thread(target=_executer, daemon=True)
    thread.start()

    def _generer():
        etapes_vues = 0
        yield f"data: {_json.dumps({'type': 'init', 'demande_id': demande_id, 'conversation_id': conversation_id})}\n\n"

        while True:
            try:
                signal = q.get(timeout=0.5)
                if signal is None:
                    break
                # Chunk LLM recu : envoyer immediatement en SSE
                if isinstance(signal, dict) and signal.get("type") == "chunk":
                    payload = {
                        "type": "chunk",
                        "texte": signal.get("texte", ""),
                    }
                    yield f"data: {_json.dumps(payload)}\n\n"
                    continue
            except queue.Empty:
                pass

            try:
                act = activity_tracker.consulter(demande_id)
                if act:
                    etapes = act.get("etapes", [])
                    for i, e in enumerate(etapes[etapes_vues:], start=etapes_vues):
                        payload = {
                            "type": "etape",
                            "index": i,
                            "message": e.get("message", ""),
                            "statut": e.get("statut", "information"),
                            "timestamp": e.get("timestamp", ""),
                        }
                        yield f"data: {_json.dumps(payload)}\n\n"
                    etapes_vues = len(etapes)
            except Exception:
                pass

        try:
            conversation_store.ajouter_message(
                conversation_id, "assistant", str(resultat_final["reponse"])
            )
        except Exception:
            pass
        payload_final = {
            "type": "final",
            "reponse": str(resultat_final["reponse"]),
            "ouvrir_url": resultat_final["ouvrir_url"],
            "succes": resultat_final["succes"],
        }
        yield f"data: {_json.dumps(payload_final)}\n\n"

    return app.response_class(
        _generer(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/conversations", methods=["GET"])
def lister_conversations():
    return jsonify(conversation_store.lister_conversations())


@app.route("/conversations/<identifiant>", methods=["GET"])
def charger_conversation(identifiant):
    messages = conversation_store.obtenir_messages(identifiant)
    if messages is None:
        return jsonify({"erreur": "Conversation introuvable."}), 404
    conversation = conversation_store.obtenir_conversation(identifiant)
    return jsonify({"conversation": conversation, "messages": messages})


@app.route("/envoyer", methods=["POST"])
def envoyer():
    message = request.form["message"]
    reponse = jarvis.traiter_commande(message, retourner_reponse=True)

    return render_template(
        "index.html",
        message=message,
        reponse=reponse
    )

@app.route("/vocal")
def vocal():
    message = voice.ecouter_et_transcrire()

    if message.startswith("Erreur"):
        reponse = message
    else:
        reponse = jarvis.traiter_commande(message, retourner_reponse=True)
        voice.parler(reponse)

    return render_template(
        "index.html",
        message=message,
        reponse=reponse
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
