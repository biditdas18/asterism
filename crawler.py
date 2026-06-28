import json
from datetime import datetime, timezone
from collections import defaultdict

from db import init_db, add_node, add_edge, strengthen_edge, get_connection

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "as", "into", "through",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "i", "me", "my", "we", "our", "you", "your", "it", "its",
    "how", "what", "when", "where", "why", "which", "who", "that", "this",
    "if", "not", "no", "so", "than", "then", "just", "more", "also",
    "get", "use", "using", "make", "like", "need", "want", "help",
}

USER_NODE = "Bidit"


def _recency_weight(updated_at: str) -> float:
    """Map conversation age to initial node weight."""
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except Exception:
        return 30.0
    age_days = (datetime.now(timezone.utc) - dt).days
    if age_days <= 30:
        return 90.0
    if age_days <= 90:
        return 70.0
    if age_days <= 180:
        return 50.0
    return 30.0


def _keywords(title: str) -> set[str]:
    """Extract significant words from a title."""
    words = set()
    for w in title.lower().split():
        w = w.strip(".,!?;:\"'()[]{}")
        if len(w) > 2 and w not in STOPWORDS:
            words.add(w)
    return words


def _set_node_weight(label: str, weight: float):
    """Upsert weight directly — add_node increments on conflict, so we patch after."""
    with get_connection() as conn:
        conn.execute("UPDATE nodes SET weight = MAX(weight, ?) WHERE label = ?", (weight, label))


def crawl_claude(path: str):
    init_db()

    with open(path, "r", encoding="utf-8") as f:
        conversations = json.load(f)

    # Ensure user node exists at full weight
    add_node(USER_NODE, node_type="user")

    # First pass: collect valid conversations with their keywords
    valid: list[tuple[str, float, set[str]]] = []
    for conv in conversations:
        name = (conv.get("name") or "").strip()
        if len(name) < 10:
            continue
        weight = _recency_weight(conv.get("updated_at", ""))
        kw = _keywords(name)
        valid.append((name, weight, kw))

    # Second pass: build nodes and user edges
    for name, weight, _ in valid:
        print(f"Processing: {name}...")
        add_node(name, node_type="concept")
        _set_node_weight(name, weight)
        add_edge(USER_NODE, name)

    # Third pass: co-occurrence edges
    # Build keyword → list of conversation names
    kw_index: dict[str, list[str]] = defaultdict(list)
    for name, _, kw in valid:
        for w in kw:
            kw_index[w].append(name)

    seen_pairs: set[frozenset] = set()
    for titles in kw_index.values():
        if len(titles) < 2:
            continue
        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                pair = frozenset({titles[i], titles[j]})
                if pair in seen_pairs:
                    strengthen_edge(titles[i], titles[j])
                else:
                    seen_pairs.add(pair)
                    add_edge(titles[i], titles[j])

    # Final stats
    with get_connection() as conn:
        n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    print(f"\nCrawled {len(valid)} conversations. Graph has {n_nodes} nodes, {n_edges} edges.")
