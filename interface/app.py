import sys
import os
import secrets

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "core"))

from flask import Flask, render_template, request, jsonify
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

@app.route("/health")
def health():
    return "ok", 200


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
    try:
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
    })


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
