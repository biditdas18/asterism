import time
import sqlite3
from datetime import datetime
from db import get_connection, init_db

INTERVAL = 60


def _decay_and_count() -> tuple[int, int]:
    node_sql = """
        DELETE FROM nodes
        WHERE (strftime('%s', 'now') - strftime('%s', last_accessed)) > ttl_seconds
        AND node_type != 'user'
    """
    edge_sql = """
        DELETE FROM edges
        WHERE (strftime('%s', 'now') - strftime('%s', last_accessed)) > ttl_seconds
    """
    with get_connection() as conn:
        nodes_removed = conn.execute(node_sql).rowcount
        edges_removed = conn.execute(edge_sql).rowcount
    return nodes_removed, edges_removed


if __name__ == "__main__":
    init_db()
    print(f"[decay_scheduler] started — interval: {INTERVAL}s")
    try:
        while True:
            nodes, edges = _decay_and_count()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] decay run — nodes removed: {nodes}, edges removed: {edges}")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\n[decay_scheduler] stopped.")
