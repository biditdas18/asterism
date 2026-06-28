import time
from datetime import datetime
from db import get_connection, init_db, decay_nodes, decay_edges

INTERVAL = 60


# ---------------------------------------------------------------------------
# Mechanic 3 — Chain Healing
# Must run BEFORE decay_nodes() so dying nodes' edges are still readable.
# ---------------------------------------------------------------------------

def _heal_chains():
    """
    For every node about to be deleted (session_seconds_exposed >= 10800):
      - Find its parents (edges pointing TO it)
      - Find its children (edges FROM it)
      - Bridge each parent → each child with weight = min(pw, cw) * 0.7
    Logged for each bridge created.
    """
    with get_connection() as conn:
        dying = conn.execute(
            "SELECT id, label FROM nodes "
            "WHERE session_seconds_exposed >= 10800 AND node_type != 'user'"
        ).fetchall()

        for node in dying:
            nid, nlabel = node["id"], node["label"]

            parents = conn.execute(
                "SELECT e.weight, n.label FROM edges e "
                "JOIN nodes n ON n.id = e.source_id WHERE e.target_id = ?", (nid,)
            ).fetchall()

            children = conn.execute(
                "SELECT e.weight, n.label FROM edges e "
                "JOIN nodes n ON n.id = e.target_id WHERE e.source_id = ?", (nid,)
            ).fetchall()

            if not parents or not children:
                continue

            for p in parents:
                for c in children:
                    bridge_w = min(p["weight"], c["weight"]) * 0.7
                    conn.execute("""
                        INSERT INTO edges (source_id, target_id, weight)
                        VALUES (
                            (SELECT id FROM nodes WHERE label = ?),
                            (SELECT id FROM nodes WHERE label = ?),
                            ?
                        )
                        ON CONFLICT(source_id, target_id) DO UPDATE SET
                            weight = MAX(weight, excluded.weight),
                            last_accessed = CURRENT_TIMESTAMP
                    """, (p["label"], c["label"], bridge_w))
                    print(
                        f"✦ Chain healed: {p['label']} → {c['label']} "
                        f"(bridge formed after {nlabel} pruned)"
                    )


# ---------------------------------------------------------------------------
# Mechanic 2 — Path Competition
# Run after structure has stabilised (after decay but before orphan check).
# ---------------------------------------------------------------------------

def _run_path_competition():
    """
    For every direct edge A→C where A→B→C also exists:
      - If direct_w > (ab_w + bc_w) / 2: accelerate B decay by +3 session seconds
      - Else: weaken direct edge by -5 weight
    """
    with get_connection() as conn:
        # find triples: direct A→C edge AND A→B→C 2-hop, B not user
        competing = conn.execute("""
            SELECT
                na.label AS a_lbl,
                nb.label AS b_lbl,
                nc.label AS c_lbl,
                ed.id    AS direct_id,
                ed.weight AS direct_w,
                e1.weight AS ab_w,
                e2.weight AS bc_w,
                nb.id    AS b_id
            FROM edges e1
            JOIN edges e2 ON e1.target_id = e2.source_id
            JOIN edges ed ON ed.source_id = e1.source_id
                          AND ed.target_id = e2.target_id
            JOIN nodes na ON na.id = e1.source_id
            JOIN nodes nb ON nb.id = e1.target_id
            JOIN nodes nc ON nc.id = e2.target_id
            WHERE nb.node_type != 'user'
        """).fetchall()

        for row in competing:
            indirect_avg = (row["ab_w"] + row["bc_w"]) / 2.0
            if row["direct_w"] > indirect_avg:
                # direct wins — accelerate B's decay
                conn.execute(
                    "UPDATE nodes SET session_seconds_exposed = session_seconds_exposed + 3 "
                    "WHERE id = ?", (row["b_id"],)
                )
                print(f"✦ Path optimizing: {row['b_lbl']} becoming redundant")
            else:
                # indirect wins — weaken the shortcut
                new_w = max(0.1, row["direct_w"] - 5)
                conn.execute(
                    "UPDATE edges SET weight = ? WHERE id = ?", (new_w, row["direct_id"])
                )


# ---------------------------------------------------------------------------
# Mechanic 4 — Orphan Detection
# Run last, after all deletions.
# ---------------------------------------------------------------------------

def _word_set(label: str) -> set[str]:
    stop = {"a","an","the","and","or","in","on","at","to","for","of","with","is","are","was"}
    return {w.lower().strip(".,!?") for w in label.split() if w.lower() not in stop and len(w) > 2}


def _rescue_orphans():
    """
    Find nodes with no path to the user node via BFS on the edge table.
    For each orphan: bridge to the most word-similar connected node (weight=20),
    or accelerate decay by -10 if no similar node found.
    """
    with get_connection() as conn:
        # find user node id
        user_row = conn.execute("SELECT id FROM nodes WHERE node_type='user' LIMIT 1").fetchone()
        if not user_row:
            return
        user_id = user_row[0]

        # build adjacency (undirected) from edges
        all_edges = conn.execute("SELECT source_id, target_id FROM edges").fetchall()
        adj: dict[int, set[int]] = {}
        for e in all_edges:
            adj.setdefault(e[0], set()).add(e[1])
            adj.setdefault(e[1], set()).add(e[0])

        # BFS from user
        reachable: set[int] = {user_id}
        queue = [user_id]
        while queue:
            cur = queue.pop()
            for nb in adj.get(cur, ()):
                if nb not in reachable:
                    reachable.add(nb)
                    queue.append(nb)

        # all nodes
        all_nodes = conn.execute("SELECT id, label, node_type FROM nodes").fetchall()
        orphans = [n for n in all_nodes if n["id"] not in reachable and n["node_type"] != "user"]
        connected = [n for n in all_nodes if n["id"] in reachable and n["node_type"] != "user"]

        for orphan in orphans:
            ow = _word_set(orphan["label"])
            best_score, best_node = 0.0, None
            for cand in connected:
                cw = _word_set(cand["label"])
                union = ow | cw
                if not union:
                    continue
                score = len(ow & cw) / len(union)
                if score > best_score:
                    best_score, best_node = score, cand

            if best_node and best_score > 0:
                conn.execute("""
                    INSERT INTO edges (source_id, target_id, weight)
                    VALUES (?, ?, 20.0)
                    ON CONFLICT(source_id, target_id) DO NOTHING
                """, (orphan["id"], best_node["id"]))
                print(f"✦ Orphan rescued: {orphan['label']} → {best_node['label']}")
            else:
                conn.execute(
                    "UPDATE nodes SET session_seconds_exposed = session_seconds_exposed + 10 "
                    "WHERE id = ?", (orphan["id"],)
                )
                print(f"✦ Orphan accelerated: {orphan['label']} (no similar node found)")


# ---------------------------------------------------------------------------
# Main decay cycle
# ---------------------------------------------------------------------------

def _decay_and_count() -> tuple[int, int]:
    # mechanic 3: heal chains before nodes are deleted
    _heal_chains()

    # edge wall-clock decay
    with get_connection() as conn:
        edge_sql = """
            DELETE FROM edges
            WHERE (strftime('%s', 'now') - strftime('%s', last_accessed)) > ttl_seconds
        """
        edges_removed = conn.execute(edge_sql).rowcount

    # node session-based decay
    before = _node_count()
    decay_nodes()
    nodes_removed = before - _node_count()

    # mechanic 2: path competition on surviving graph
    _run_path_competition()

    # mechanic 4: orphan rescue after all deletions
    _rescue_orphans()

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
