import json
import webbrowser
from datetime import datetime, timezone
from collections import defaultdict

from db import init_db, add_node, add_edge, get_connection
from config import load_config

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


def _recency_weight(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return 30.0
    age_days = (datetime.now(timezone.utc) - dt).days
    if age_days <= 30:   return 90.0
    if age_days <= 90:   return 70.0
    if age_days <= 180:  return 50.0
    return 30.0


def _set_node_weight(label: str, weight: float):
    with get_connection() as conn:
        conn.execute(
            "UPDATE nodes SET weight = MAX(weight, ?) WHERE label = ?",
            (weight, label),
        )


def _call_haiku(api_key: str, convs: list[dict]) -> list[dict] | None:
    """
    Single Haiku call. Returns a list of domain dicts or None on failure.
    Uses assistant prefill of '{' to guarantee raw JSON (no markdown fences).
    Schema: [{"name": "Domain", "themes": [{"name": "Theme", "chain": ["t1","t2"]}]}]
    """
    try:
        import anthropic

        titles_list = "\n".join(
            f"{i+1}. [{c['created_at'][:10]}] {c['title']}"
            for i, c in enumerate(convs)
        )

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=(
                "You are an expert at understanding how human thoughts evolve over time. "
                "Return ONLY valid JSON arrays/objects. No markdown, no explanation."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Group these chronological conversation titles into a 3-level hierarchy "
                        "that shows how thinking evolved over time.\n\n"
                        "Return a JSON array where each element is a domain:\n"
                        '[{"name":"Domain","themes":[{"name":"Theme","chain":["title1","title2"]}]}]\n\n'
                        "Rules:\n"
                        "- 3 to 6 domains (broad life areas, intuitive names)\n"
                        "- 2 to 5 themes per domain (specific, not generic)\n"
                        "- chain = conversation titles in causal/chronological order\n"
                        "- every title must appear exactly once\n"
                        "- preserve exact title strings\n\n"
                        f"Conversations:\n{titles_list}"
                    ),
                },
                # prefill forces the model to continue from '[' — no markdown fences possible
                {"role": "assistant", "content": "["},
            ],
        )

        raw = "[" + msg.content[0].text.strip().rstrip("```").strip()
        domains = json.loads(raw)
        if not isinstance(domains, list) or not domains:
            return None
        return domains

    except Exception as e:
        print(f"  (Haiku error: {e})")
        return None


def _build_hierarchy(
    convs: list[dict],
    domains: list[dict],
    user_node: str,
) -> tuple[int, int, int]:
    """
    Construct graph:  user → domain → theme → conv1 → conv2 → …
    domains is the list returned by _call_haiku.
    Returns (n_domains, n_themes, n_convs_placed).
    """
    weight_map = {c["title"]: c["weight"] for c in convs}
    placed: set[str] = set()
    n_domains = n_themes = n_convs = 0

    for domain in domains:
        domain_name = domain.get("name", "").strip()
        themes = domain.get("themes", [])
        if not domain_name or not themes:
            continue

        domain_weights = [
            weight_map[t]
            for theme in themes
            for t in theme.get("chain", [])
            if t in weight_map
        ]
        domain_weight = (sum(domain_weights) / len(domain_weights)) if domain_weights else 50.0

        add_node(domain_name, node_type="domain")
        _set_node_weight(domain_name, max(domain_weight, 80.0))
        add_edge(user_node, domain_name)
        n_domains += 1

        for theme in themes:
            theme_name = theme.get("name", "").strip()
            chain = [t for t in theme.get("chain", []) if t in weight_map]
            if not theme_name or not chain:
                continue

            theme_weight = sum(weight_map[t] for t in chain) / len(chain)
            add_node(theme_name, node_type="theme")
            _set_node_weight(theme_name, theme_weight)
            add_edge(domain_name, theme_name)
            n_themes += 1

            prev = theme_name
            for title in chain:
                add_node(title, node_type="concept")
                _set_node_weight(title, weight_map[title])
                add_edge(prev, title)
                placed.add(title)
                prev = title
                n_convs += 1

    # titles Haiku missed: attach to user
    for c in convs:
        if c["title"] not in placed:
            add_node(c["title"], node_type="concept")
            _set_node_weight(c["title"], c["weight"])
            add_edge(user_node, c["title"])
            n_convs += 1

    return n_domains, n_themes, n_convs


def _build_flat(convs: list[dict], user_node: str):
    """Flat star fallback — all titles connect directly to user."""
    from collections import defaultdict
    from db import strengthen_edge

    kw_index: dict[str, list[str]] = defaultdict(list)
    for c in convs:
        add_node(c["title"], node_type="concept")
        _set_node_weight(c["title"], c["weight"])
        add_edge(user_node, c["title"])
        for w in _keywords(c["title"]):
            kw_index[w].append(c["title"])

    seen: set[frozenset] = set()
    for group in kw_index.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                pair = frozenset({group[i], group[j]})
                if pair in seen:
                    strengthen_edge(group[i], group[j])
                else:
                    seen.add(pair)
                    add_edge(group[i], group[j])


def _keywords(title: str) -> set[str]:
    words = set()
    for w in title.lower().split():
        w = w.strip(".,!?;:\"'()[]{}")
        if len(w) > 2 and w not in STOPWORDS:
            words.add(w)
    return words


def crawl_claude(path: str):
    init_db()

    config = load_config()
    user_node = config.get("user_name", "Bidit")
    api_key = config.get("anthropic_api_key", "")

    with open(path, "r", encoding="utf-8") as f:
        raw_convs = json.load(f)

    # sort chronologically; filter short names
    raw_convs.sort(key=lambda c: c.get("created_at", ""))
    convs = []
    for c in raw_convs:
        title = (c.get("name") or "").strip()
        if len(title) < 8:
            continue
        convs.append({
            "title": title,
            "created_at": c.get("created_at", ""),
            "weight": _recency_weight(c.get("created_at", "")),
        })

    add_node(user_node, node_type="user")

    print(f"✦ Found {len(convs)} conversations. Building causal graph via Haiku...")

    domains = None
    if api_key:
        domains = _call_haiku(api_key, convs)

    if domains:
        n_domains, n_themes, n_convs = _build_hierarchy(convs, domains, user_node)
    else:
        print("✦ Clustering failed, using flat graph")
        _build_flat(convs, user_node)
        n_domains = n_themes = 0
        n_convs = len(convs)

    with get_connection() as conn:
        n_nodes = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        n_edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]

    # summary
    print("\n✦ Asterism crawled successfully\n")
    if domains:
        print(" Domains detected:")
        for domain in domains:
            dname = domain.get("name", "?")
            themes = domain.get("themes", [])
            n_conv_in_domain = sum(len(t.get("chain", [])) for t in themes)
            print(f"   ✦ {dname} ({len(themes)} themes, {n_conv_in_domain} conversations)")
        print(f"\n Total: {n_domains} domains, {n_themes} themes, {n_convs} conversation nodes")
    print(f" Graph: {n_nodes} nodes, {n_edges} edges\n")

    from render import render_graph
    html_path = render_graph()
    print("✦ Opening your constellation...")
    webbrowser.open(f"file://{html_path}")
