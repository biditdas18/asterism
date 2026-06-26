import time
from datetime import datetime
from db import get_connection, init_db, decay_nodes, decay_edges

INTERVAL = 60


def _decay_and_count() -> tuple[int, int]:
    # edges still use wall-clock TTL (unchanged per spec)
    edge_sql = """
        DELETE FROM edges
        WHERE (strftime('%s', 'now') - strftime('%s', last_accessed)) > ttl_seconds
    """
    with get_connection() as conn:
        edges_removed = conn.execute(edge_sql).rowcount

    # nodes use session-based decay (session_seconds_exposed >= 10800)
    before = _node_count()
    decay_nodes()
    nodes_removed = before - _node_count()
    return nodes_removed, edges_removed


def _node_count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM nodes WHERE node_type != 'user'").fetchone()[0]


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
