"""Index SQLite FTS5 pour recherche pertinence dans memory.json."""
import json
import os
import sqlite3
from datetime import datetime

from core import chemins

CHEMIN_MEMORY = chemins.chemin_memory_json()
CHEMIN_INDEX = chemins.chemin_memory_index()


def _charger_memory():
    if not os.path.exists(CHEMIN_MEMORY):
        return []
    try:
        with open(CHEMIN_MEMORY, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return (
                data.get("echanges")
                or data.get("conversations")
                or data.get("historique", [])
            )
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _connecter():
    os.makedirs(os.path.dirname(CHEMIN_INDEX), exist_ok=True)
    conn = sqlite3.connect(CHEMIN_INDEX)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS echanges
        USING fts5(question, reponse, categorie, timestamp UNINDEXED, tokenize='unicode61')
    """)
    return conn


def indexer_tout(force=False):
    """Reindexe tous les echanges depuis memory.json."""
    echanges = _charger_memory()
    conn = _connecter()
    if force:
        conn.execute("DELETE FROM echanges")
    # Compter deja indexes
    cur = conn.execute("SELECT COUNT(*) FROM echanges")
    deja = cur.fetchone()[0]
    ajoutes = 0
    for i, e in enumerate(echanges):
        if i < deja and not force:
            continue
        q = str(e.get("question", ""))[:2000]
        r = str(e.get("reponse", ""))[:5000]
        c = str(e.get("categorie", "conversation"))
        ts = str(e.get("timestamp", e.get("date", "")))
        if not q:
            continue
        conn.execute(
            "INSERT INTO echanges (question, reponse, categorie, timestamp) VALUES (?, ?, ?, ?)",
            (q, r, c, ts),
        )
        ajoutes += 1
    conn.commit()
    conn.close()
    return {"total": len(echanges), "deja": deja, "ajoutes": ajoutes}


def indexer_echange(question, reponse, categorie="conversation", timestamp=None):
    """Indexe un seul echange (appele apres ajout dans memory.json)."""
    if not question:
        return False
    conn = _connecter()
    try:
        from datetime import datetime
        ts = timestamp or datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "INSERT INTO echanges (question, reponse, categorie, timestamp) VALUES (?, ?, ?, ?)",
            (str(question)[:2000], str(reponse)[:5000], str(categorie), str(ts)),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def rechercher(mot_cle, limite=5):
    """Recherche par pertinence (BM25). Retourne liste de dict."""
    if not mot_cle or len(str(mot_cle).strip()) < 2:
        return []
    # Nettoyer la requete pour FTS5 (enlever caracteres speciaux)
    import re
    q = re.sub(r"[^\w\s]", " ", str(mot_cle)).strip()
    if not q:
        return []
    conn = _connecter()
    try:
        cur = conn.execute("""
            SELECT question, reponse, categorie, timestamp, rank
            FROM echanges
            WHERE echanges MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (q, limite))
        resultats = []
        for row in cur.fetchall():
            resultats.append({
                "question": row[0],
                "reponse": row[1],
                "categorie": row[2],
                "timestamp": row[3],
                "pertinence": round(-row[4], 3) if row[4] else 0,
            })
        return resultats
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def etat():
    conn = _connecter()
    try:
        n = conn.execute("SELECT COUNT(*) FROM echanges").fetchone()[0]
        return {"indexes": n, "chemin": CHEMIN_INDEX}
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "rebuild":
        print(indexer_tout(force=True))
    elif len(sys.argv) > 1:
        print("Recherche:", sys.argv[1])
        for r in rechercher(sys.argv[1]):
            print(f"  [{r['pertinence']}] {r['question'][:80]}")
    else:
        print("Etat:", etat())
        print("Index:", indexer_tout())
