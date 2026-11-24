import sys
import os
import hmac
import hashlib
import math
import secrets
import tempfile
import queue
import threading
import time
import json as _json
from datetime import timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "core"))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from io import BytesIO
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    send_from_directory,
    redirect,
    session,
    url_for,
    has_request_context,
)
from jarvis import Jarvis
from voice_manager import VoiceManager
from activity_tracker import ActivityTracker
from interface.conversation_store import ConversationStore

app = Flask(__name__)

jarvis = Jarvis()
voice = VoiceManager()
activity_tracker = ActivityTracker()
conversation_store = ConversationStore()


# ---------------------------------------------------------------------------
# Authentification web (C1)
#
# Activee uniquement si JARVIS_WEB_PASSWORD est defini (vide = acces local
# libre, comportement historique). La cle de signature des cookies vient de
# JARVIS_SECRET_KEY ; a defaut une cle aleatoire est generee a chaque demarrage
# (les sessions sont alors invalidees au redemarrage).
# ---------------------------------------------------------------------------

_VARIABLE_MOT_DE_PASSE = "JARVIS_WEB_PASSWORD"
_VARIABLE_CLE_SESSION = "JARVIS_SECRET_KEY"
_VARIABLE_MAX_TENTATIVES = "JARVIS_LOGIN_MAX_TENTATIVES"
_VARIABLE_FENETRE_CONNEXIONS = "JARVIS_LOGIN_FENETRE_SECONDES"
_VARIABLE_BLOCAGE_CONNEXIONS = "JARVIS_LOGIN_BLOCAGE_SECONDES"

# Limitation des tentatives de connexion, en memoire et par adresse cliente.
# Volontairement sans dependance : suffisant pour un deploiement mono-processus.
_LIMITE_MAX_TENTATIVES_DEFAUT = 5
_LIMITE_FENETRE_DEFAUT = 15 * 60
_LIMITE_BLOCAGE_DEFAUT = 15 * 60
_LIMITE_ENTREES_MAX = 2048
_limite_connexions = {}
_limite_verrou = threading.Lock()

# Routes accessibles sans etre authentifie.
_ENDPOINTS_PUBLICS = {
    "connexion",
    "deconnexion",
    "health",
    "static",
    "service_worker",
}

app.secret_key = os.environ.get(_VARIABLE_CLE_SESSION) or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("JARVIS_WEB_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)


def _mot_de_passe_attendu():
    """Mot de passe attendu, lu a chaque requete (permet de le changer)."""
    return os.environ.get(_VARIABLE_MOT_DE_PASSE, "")


def _authentification_active():
    return bool(_mot_de_passe_attendu())


def _empreinte_mot_de_passe():
    return hashlib.sha256(_mot_de_passe_attendu().encode("utf-8")).hexdigest()


def _session_valide():
    empreinte = session.get("empreinte")
    return (
        session.get("authentifie") is True
        and isinstance(empreinte, str)
        and bool(empreinte)
        and hmac.compare_digest(empreinte, _empreinte_mot_de_passe())
    )


def _destination_sure(valeur):
    """N'accepte qu'un chemin interne, jamais une redirection externe."""
    if not isinstance(valeur, str) or not valeur or len(valeur) > 2000:
        return None
    if not valeur.startswith("/") or valeur.startswith("//"):
        return None
    if "\\" in valeur or "\n" in valeur or "\r" in valeur:
        return None
    return valeur


def _attend_une_reponse_json():
    return (
        request.is_json
        or request.path.startswith(("/api/", "/chat", "/conversations", "/activite"))
    )


def _entier_environment(nom, defaut):
    try:
        valeur = int(os.environ.get(nom, defaut))
    except (TypeError, ValueError):
        return defaut
    return max(1, valeur)


def _cle_client():
    return request.remote_addr or "inconnu"


def _nettoyer_limite(maintenant, fenetre):
    """Borne la memoire : oublie les clients sans echec recent ni blocage."""
    if len(_limite_connexions) <= _LIMITE_ENTREES_MAX:
        return
    for adresse, etat in list(_limite_connexions.items()):
        if etat["bloque_jusqua"] <= maintenant and not any(
            maintenant - instant < fenetre for instant in etat["echecs"]
        ):
            _limite_connexions.pop(adresse, None)


def _secondes_de_blocage():
    """Renvoie le temps de blocage restant, ou 0 si la connexion est permise."""
    adresse = _cle_client()
    maintenant = time.monotonic()
    fenetre = _entier_environment(_VARIABLE_FENETRE_CONNEXIONS, _LIMITE_FENETRE_DEFAUT)

    with _limite_verrou:
        etat = _limite_connexions.get(adresse)
        if etat is None:
            return 0
        if etat["bloque_jusqua"] > maintenant:
            return max(1, math.ceil(etat["bloque_jusqua"] - maintenant))
        if etat["bloque_jusqua"]:
            # Le blocage a expire : on repart d'une ardoise propre.
            _limite_connexions.pop(adresse, None)
            return 0
        etat["echecs"] = [
            instant for instant in etat["echecs"] if maintenant - instant < fenetre
        ]
        if not etat["echecs"]:
            _limite_connexions.pop(adresse, None)
        return 0


def _enregistrer_echec_connexion():
    """Compte un echec ; renvoie la duree de blocage si le seuil est atteint."""
    adresse = _cle_client()
    maintenant = time.monotonic()
    fenetre = _entier_environment(_VARIABLE_FENETRE_CONNEXIONS, _LIMITE_FENETRE_DEFAUT)
    maximum = _entier_environment(_VARIABLE_MAX_TENTATIVES, _LIMITE_MAX_TENTATIVES_DEFAUT)
    duree = _entier_environment(_VARIABLE_BLOCAGE_CONNEXIONS, _LIMITE_BLOCAGE_DEFAUT)

    with _limite_verrou:
        _nettoyer_limite(maintenant, fenetre)
        etat = _limite_connexions.setdefault(
            adresse, {"echecs": [], "bloque_jusqua": 0.0}
        )
        etat["echecs"] = [
            instant for instant in etat["echecs"] if maintenant - instant < fenetre
        ]
        etat["echecs"].append(maintenant)
        if len(etat["echecs"]) >= maximum:
            etat["echecs"].clear()
            etat["bloque_jusqua"] = maintenant + duree
            return duree
        return 0


def _reinitialiser_limite_connexions(adresse=None):
    """Oublie les echecs (connexion reussie, ou remise a zero explicite)."""
    if adresse is None and has_request_context():
        adresse = _cle_client()
    with _limite_verrou:
        if adresse is None:
            _limite_connexions.clear()
        else:
            _limite_connexions.pop(adresse, None)


def _message_blocage(secondes):
    minutes = max(1, math.ceil(secondes / 60))
    return (
        "Trop de tentatives de connexion. "
        f"Reessaie dans {minutes} minute{'s' if minutes > 1 else ''}."
    )


def _jeton_csrf():
    jeton = session.get("csrf")
    if not isinstance(jeton, str) or not jeton:
        jeton = secrets.token_urlsafe(32)
        session["csrf"] = jeton
    return jeton


def _csrf_valide():
    recu = request.form.get("csrf", "")
    attendu = session.get("csrf", "")
    return (
        isinstance(recu, str)
        and isinstance(attendu, str)
        and bool(recu)
        and hmac.compare_digest(recu, attendu)
    )


@app.before_request
def _exiger_authentification():
    if not _authentification_active():
        return None
    if request.endpoint in _ENDPOINTS_PUBLICS:
        return None
    if _session_valide():
        return None

    if _attend_une_reponse_json():
        return jsonify({"erreur": "Authentification requise."}), 401

    suivant = request.full_path if request.query_string else request.path
    return redirect(url_for("connexion", suivant=suivant))


@app.route("/login", methods=["GET", "POST"])
def connexion():
    if not _authentification_active():
        return redirect(url_for("accueil"))

    suivant = _destination_sure(request.values.get("suivant")) or url_for("accueil")
    erreur = None

    if request.method == "POST":
        if not _csrf_valide():
            return render_template(
                "login.html",
                erreur="Formulaire expire. Reessaie.",
                suivant=suivant,
                csrf=_jeton_csrf(),
            ), 400

        blocage = _secondes_de_blocage()
        if blocage:
            return render_template(
                "login.html",
                erreur=_message_blocage(blocage),
                suivant=suivant,
                csrf=_jeton_csrf(),
            ), 429, {"Retry-After": str(blocage)}

        fourni = request.form.get("mot_de_passe", "")
        if isinstance(fourni, str) and hmac.compare_digest(
            fourni, _mot_de_passe_attendu()
        ):
            _reinitialiser_limite_connexions()
            session.clear()
            session["authentifie"] = True
            session["empreinte"] = _empreinte_mot_de_passe()
            session.permanent = True
            return redirect(suivant)

        duree = _enregistrer_echec_connexion()
        if duree:
            return render_template(
                "login.html",
                erreur=_message_blocage(duree),
                suivant=suivant,
                csrf=_jeton_csrf(),
            ), 429, {"Retry-After": str(duree)}

        erreur = "Mot de passe incorrect."

    return render_template(
        "login.html", erreur=erreur, suivant=suivant, csrf=_jeton_csrf()
    ), (401 if erreur else 200)


@app.route("/deconnexion", methods=["GET", "POST"])
def deconnexion():
    session.clear()
    return redirect(url_for("connexion"))


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


@app.route("/api/missions", methods=["GET"])
def lister_missions():
    statut = request.args.get("statut")
    missions = jarvis.mission_manager.lister_missions()
    if statut:
        missions = [m for m in missions if m.get("statut") == statut]
    return jsonify({"missions": missions, "nombre": len(missions)})


@app.route("/api/missions/<mission_id>", methods=["GET"])
def obtenir_mission_route(mission_id):
    mission = jarvis.mission_manager.obtenir_mission(mission_id)
    if mission is None:
        return jsonify({"erreur": "Mission introuvable"}), 404
    mission_copy = dict(mission)
    sous_taches = jarvis.mission_manager.obtenir_sous_taches(mission_id)
    mission_copy["sous_taches"] = sous_taches
    return jsonify(mission_copy)


@app.route("/api/apprentissages", methods=["GET"])
def lister_apprentissages():
    chemin = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "apprentissages.json"))
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = _json.load(f)
    except FileNotFoundError:
        return jsonify({"erreur": "Fichier introuvable"}), 404
    except ValueError:
        return jsonify({"erreur": "JSON invalide"}), 500
    return jsonify(data)


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
    if not _authentification_active():
        app.logger.warning(
            "%s non defini : l'interface web est accessible sans authentification.",
            _VARIABLE_MOT_DE_PASSE,
        )
    app.run(host="0.0.0.0", port=5000)
