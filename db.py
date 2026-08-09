import sqlite3
import os
from datetime import datetime

try:
    from config import get_db_path
    DB_PATH = get_db_path()
except Exception:
    DB_PATH = os.path.join(os.path.dirname(__file__), "asterism.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database from schema.sql."""
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()
    with get_connection() as conn:
        conn.executescript(schema)
        # migration: add column for existing DBs
        try:
            conn.execute("ALTER TABLE nodes ADD COLUMN session_seconds_exposed INTEGER DEFAULT 0")
        except Exception:
            pass  # column already exists
    print(f"DB initialized at {DB_PATH}")


# --- NODE CRUD ---

# --- embedding fallback for _resolve_label ---
# Local, offline (ONNX via fastembed — no torch, no network calls after the
# one-time ~67MB model download). Lazily loaded: only paid by callers that
# actually reach the embedding fallback (i.e. add_node() on a cache miss),
# never by pure reads like llm._load_graph_data().
_EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
_EMBED_SIMILARITY_THRESHOLD = 0.92  # see calibration notes below _embedding_match
_embed_model = None
_embed_cache: dict[str, "list[float]"] = {}


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding
        _embed_model = TextEmbedding(model_name=_EMBED_MODEL_NAME)
    return _embed_model


def _embed_texts(texts: list[str]) -> list:
    return list(_get_embed_model().embed(texts))


def _embedding_match(label: str, existing_labels: list[str]) -> str | None:
    """
    Second-pass fallback for _resolve_label: catches same-concept labels
    the prefix pass misses (mid-string edits, reordered phrasing, or
    short labels below the prefix pass's 10-char guard).

    ponytail: calibrated against the live ~50-node asterism.db (see
    poc_results.json-era dataset) — at threshold 0.92 it catches every
    real near-duplicate in that DB (0.93-0.98 range: "CLI Tools"/"CLI
    tool", "AI Memory Tools"/"AI memory tooling", "LLM context
    limitations"/"...window limitations") with zero false merges (highest
    genuinely-distinct pair topped out at 0.885: "Knowledge graph
    architecture research"/"knowledge graphs"). Known ceiling: it's good
    at reworded/reordered phrasing that reuses the same vocabulary, but
    true synonym substitution (different words for the same thing, e.g.
    "LLM" vs "Large Language Models", "GPUs" vs "graphics processors")
    scores 0.58-0.80 on this model — below the safe threshold, so those
    stay unmerged rather than risk false merges. Upgrade path: a
    larger/instruction-tuned local model or an API-embedding fallback
    (flagged, not implemented — needs confirmation before adding cost).
    """
    if not existing_labels:
        return None
    try:
        import numpy as np

        to_embed = [l for l in existing_labels if l not in _embed_cache]
        if to_embed:
            for l, v in zip(to_embed, _embed_texts(to_embed)):
                _embed_cache[l] = v
        if label not in _embed_cache:
            _embed_cache[label] = _embed_texts([label])[0]

        cand = np.array(_embed_cache[label])
        cand_norm = np.linalg.norm(cand)
        best_label, best_score = None, 0.0
        for existing in existing_labels:
            v = np.array(_embed_cache[existing])
            score = float(np.dot(cand, v) / (cand_norm * np.linalg.norm(v)))
            if score > best_score:
                best_label, best_score = existing, score
        if best_score >= _EMBED_SIMILARITY_THRESHOLD:
            return best_label
    except Exception:
        pass
    return None


def _resolve_label(label: str, conn: sqlite3.Connection) -> str:
    """
    Map a proposed label onto an existing near-duplicate so callers
    strengthen the existing node instead of forking a new one per
    LLM-extracted phrasing. Two passes:
      1. exact/prefix match (fast, no model) - case/whitespace variants
         and "X" vs "X reading"/"X process" style extractor variants.
      2. embedding similarity fallback (see _embedding_match) for
         same-concept labels that don't share a prefix.
    """
    existing_labels = [row["label"] for row in conn.execute("SELECT label FROM nodes").fetchall()]
    norm = " ".join(label.strip().lower().split())
    for existing in existing_labels:
        existing_norm = " ".join(existing.strip().lower().split())
        if existing_norm == norm:
            return existing
        shorter, longer = (
            (norm, existing_norm) if len(norm) <= len(existing_norm)
            else (existing_norm, norm)
        )
        if len(shorter) >= 10 and longer.startswith(shorter):
            return existing

    embedding_match = _embedding_match(label, existing_labels)
    if embedding_match:
        return embedding_match

    return label


def add_node(label: str, node_type: str = "concept", ttl_seconds: int = 604800) -> int:
    default_weight = 100.0 if node_type == "user" else 1.0
    sql = """
        INSERT INTO nodes (label, node_type, ttl_seconds, weight)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(label) DO UPDATE SET
            last_accessed = CURRENT_TIMESTAMP,
            weight = CASE WHEN node_type = 'user' THEN MAX(weight, 100.0)
                          ELSE weight + 0.1 END
        RETURNING id
    """
    with get_connection() as conn:
        resolved_label = _resolve_label(label, conn)
        row = conn.execute(sql, (resolved_label, node_type, ttl_seconds, default_weight)).fetchone()
        return row["id"]


def get_node(label: str) -> dict | None:
    sql = "SELECT * FROM nodes WHERE label = ?"
    with get_connection() as conn:
        row = conn.execute(sql, (label,)).fetchone()
        return dict(row) if row else None


def delete_node(label: str) -> bool:
    sql = "DELETE FROM nodes WHERE label = ?"
    with get_connection() as conn:
        cur = conn.execute(sql, (label,))
        return cur.rowcount > 0


def add_session_time(seconds: int):
    """Accumulate session exposure time on all non-user nodes."""
    sql = "UPDATE nodes SET session_seconds_exposed = session_seconds_exposed + ? WHERE node_type != 'user'"
    with get_connection() as conn:
        conn.execute(sql, (seconds,))


def decay_nodes():
    """Delete non-user nodes that have accumulated 3h of session exposure without traversal."""
    sql = "DELETE FROM nodes WHERE session_seconds_exposed >= 10800 AND node_type != 'user'"
    with get_connection() as conn:
        cur = conn.execute(sql)
        print(f"Decayed {cur.rowcount} expired nodes.")


# --- EDGE CRUD ---

def add_edge(source_label: str, target_label: str, ttl_seconds: int = 604800) -> int:
    source_id = add_node(source_label)
    target_id = add_node(target_label)
    sql = """
        INSERT INTO edges (source_id, target_id, ttl_seconds)
        VALUES (?, ?, ?)
        ON CONFLICT(source_id, target_id) DO UPDATE SET
            last_accessed = CURRENT_TIMESTAMP,
            weight = weight + 0.1
        RETURNING id
    """
    with get_connection() as conn:
        row = conn.execute(sql, (source_id, target_id, ttl_seconds)).fetchone()
        return row["id"]


def get_edges(label: str) -> list[dict]:
    sql = """
        SELECT e.*, n1.label AS source_label, n2.label AS target_label
        FROM edges e
        JOIN nodes n1 ON e.source_id = n1.id
        JOIN nodes n2 ON e.target_id = n2.id
        WHERE n1.label = ? OR n2.label = ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (label, label)).fetchall()
        return [dict(r) for r in rows]


def delete_edge(source_label: str, target_label: str) -> bool:
    sql = """
        DELETE FROM edges
        WHERE source_id = (SELECT id FROM nodes WHERE label = ?)
        AND target_id = (SELECT id FROM nodes WHERE label = ?)
    """
    with get_connection() as conn:
        cur = conn.execute(sql, (source_label, target_label))
        return cur.rowcount > 0


def decay_edges():
    """Delete edges whose TTL has expired since last_accessed."""
    sql = """
        DELETE FROM edges
        WHERE (strftime('%s', 'now') - strftime('%s', last_accessed)) > ttl_seconds
    """
    with get_connection() as conn:
        cur = conn.execute(sql)
        print(f"Decayed {cur.rowcount} expired edges.")


def strengthen_edge(source_label: str, target_label: str, delta: float = 0.2):
    """Called when LLM traverses this edge. Resets TTL and increases weight."""
    edge_sql = """
        UPDATE edges
        SET weight = weight + ?,
            last_accessed = CURRENT_TIMESTAMP
        WHERE source_id = (SELECT id FROM nodes WHERE label = ?)
        AND target_id = (SELECT id FROM nodes WHERE label = ?)
    """
    reset_sql = "UPDATE nodes SET session_seconds_exposed = 0 WHERE label IN (?, ?)"
    with get_connection() as conn:
        conn.execute(edge_sql, (delta, source_label, target_label))
        conn.execute(reset_sql, (source_label, target_label))
