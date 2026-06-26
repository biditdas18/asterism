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
        row = conn.execute(sql, (label, node_type, ttl_seconds, default_weight)).fetchone()
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
