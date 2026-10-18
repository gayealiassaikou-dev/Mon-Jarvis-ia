"""Stockage SQLite des conversations de Sam Sarr."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


DOSSIER_DONNEES = Path(__file__).resolve().parent / "data"
FICHIER_BASE = DOSSIER_DONNEES / "conversations.db"


def maintenant():
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    """Gestion persistante des conversations et de leurs messages."""

    def __init__(self, chemin=None):
        self.chemin = Path(chemin) if chemin else FICHIER_BASE
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self.initialiser()

    def connexion(self):
        connexion = sqlite3.connect(str(self.chemin), timeout=10)
        connexion.row_factory = sqlite3.Row
        connexion.execute("PRAGMA foreign_keys = ON")
        return connexion

    def initialiser(self):
        with self.connexion() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    titre TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(id)
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                ON messages(conversation_id, id)
            """)

    @staticmethod
    def creer_titre(message):
        titre = " ".join((message or "").split())
        if len(titre) > 60:
            titre = titre[:57].rstrip() + "..."
        return titre or "Nouvelle discussion"

    def creer_conversation(self, premier_message):
        identifiant = uuid.uuid4().hex
        date = maintenant()
        with self.connexion() as db:
            db.execute(
                """INSERT INTO conversations
                   (id, titre, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (identifiant, self.creer_titre(premier_message), date, date),
            )
        return self.obtenir_conversation(identifiant)

    def lister_conversations(self):
        with self.connexion() as db:
            lignes = db.execute("""
                SELECT c.id, c.titre, c.created_at, c.updated_at,
                       COUNT(m.id) AS nombre_messages
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            """).fetchall()
        return [dict(ligne) for ligne in lignes]

    def obtenir_conversation(self, identifiant):
        with self.connexion() as db:
            ligne = db.execute(
                """SELECT id, titre, created_at, updated_at
                   FROM conversations WHERE id = ?""",
                (identifiant,),
            ).fetchone()
        return dict(ligne) if ligne else None

    def obtenir_messages(self, identifiant):
        with self.connexion() as db:
            existe = db.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (identifiant,)
            ).fetchone()
            if not existe:
                return None
            lignes = db.execute(
                """SELECT id, role, content, created_at
                   FROM messages WHERE conversation_id = ?
                   ORDER BY id""",
                (identifiant,),
            ).fetchall()
        return [dict(ligne) for ligne in lignes]

    def ajouter_message(self, identifiant, role, contenu):
        if role not in ("user", "assistant"):
            raise ValueError("Rôle de message invalide.")
        date = maintenant()
        with self.connexion() as db:
            curseur = db.execute(
                """INSERT INTO messages
                   (conversation_id, role, content, created_at)
                   SELECT id, ?, ?, ? FROM conversations WHERE id = ?""",
                (role, str(contenu), date, identifiant),
            )
            if curseur.rowcount == 0:
                raise ValueError("Conversation introuvable.")
            db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (date, identifiant),
            )
        return True
