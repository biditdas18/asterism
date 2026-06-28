import os
import sys
# ensure the project root is on sys.path when invoked via installed script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subprocess
import webbrowser
import click
from config import load_config, save_config, is_configured, get_db_path, CONFIG_DIR


def _write_env_key(env_path: str, key: str, value: str):
    """Upsert a KEY=value line in an .env file."""
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)


@click.group()
def cli():
    """✦ Asterism — an X-ray of your brain."""


@cli.command()
def init():
    """Set up Asterism for the first time."""
    click.echo("\n✦ Welcome to Asterism\n")

    # Step 1: name
    name = click.prompt("Your name (this becomes your central node)").strip()
    if not name:
        name = "You"

    # Step 2: API key with format validation loop
    while True:
        api_key = click.prompt("Anthropic API key (sk-ant-...)", hide_input=True).strip()
        if api_key.startswith("sk-ant-"):
            break
        click.echo("  ✗ Key must start with sk-ant-  — try again.")

    config = load_config()
    config["anthropic_api_key"] = api_key
    config["user_name"] = name
    config["extractor_mode"] = "haiku"

    os.makedirs(CONFIG_DIR, exist_ok=True)

    # write key to .env in cwd for dotenv compatibility
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    _write_env_key(env_path, "ANTHROPIC_API_KEY", api_key)

    # init DB silently
    import db as _db
    _db.DB_PATH = get_db_path()
    _db.init_db()

    save_config(config)

    click.echo(f"\n✦ Export your Claude conversations:")
    click.echo("   → Go to: claude.ai/settings")
    click.echo("   → Click Account → Export Data")
    click.echo("   → Check your email for the download link")
    click.echo("   → Unzip the file")
    click.echo("")
    click.echo("   Once downloaded, run:")
    click.echo("     asterism crawl --source claude --path /path/to/conversations.json")
    click.echo("")
    click.echo("   Then run:")
    click.echo("     asterism view")
    click.echo("")
    click.echo("   Your constellation will open automatically.")
    click.echo(f"\n✦ Asterism ready. Your constellation awaits.\n")


def _build_chat_system_prompt(user_name: str) -> str:
    """Serialize top-50 graph nodes + causal chains into a claude.ai system prompt."""
    from db import get_connection

    with get_connection() as conn:
        nodes = conn.execute(
            "SELECT label, weight, node_type FROM nodes ORDER BY weight DESC LIMIT 50"
        ).fetchall()
        edges = conn.execute("""
            SELECT n_src.label AS src, n_tgt.label AS tgt, e.weight AS w
            FROM edges e
            JOIN nodes n_src ON n_src.id = e.source_id
            JOIN nodes n_tgt ON n_tgt.id = e.target_id
            ORDER BY e.weight DESC
        """).fetchall()

    # active nodes block
    node_lines = "\n".join(
        f"- {n['label']} (weight: {n['weight']:.0f}, type: {n['node_type']})"
        for n in nodes
    )

    # causal chains: walk domain → theme → concept using edge order
    # build children map from edges
    children: dict[str, list[tuple[float, str]]] = {}
    for e in edges:
        children.setdefault(e["src"], []).append((e["w"], e["tgt"]))
    for k in children:
        children[k].sort(reverse=True)

    node_type = {n["label"]: n["node_type"] for n in nodes}

    chain_lines = []
    for n in nodes:
        if n["node_type"] != "domain":
            continue
        domain = n["label"]
        for _, theme in children.get(domain, []):
            if node_type.get(theme) != "theme":
                continue
            concepts = [lbl for _, lbl in children.get(theme, [])
                        if node_type.get(lbl) == "concept"]
            if concepts:
                chain_lines.append(f"{domain} → {theme} → " + " → ".join(concepts[:4]))

    chains_block = "\n".join(chain_lines) if chain_lines else "(no chains yet — run asterism crawl first)"

    return (
        f"You are chatting with {user_name}. "
        f"You have access to their personal knowledge graph "
        f"built from their conversation history.\n\n"
        f"Respond to all messages with awareness of this context. "
        f"When relevant, reference their priorities naturally.\n\n"
        f"When the user types '✦ traversal' or 'show traversal', "
        f"display which nodes informed your last response.\n\n"
        f"ACTIVE KNOWLEDGE GRAPH:\n{node_lines}\n\n"
        f"CAUSAL CHAINS:\n{chains_block}"
    )


@cli.command()
def chat():
    """Open Asterism chat in browser with graph context pre-injected."""
    if not is_configured():
        click.echo("Run asterism init first.")
        sys.exit(1)

    config = load_config()
    user_name = config.get("user_name", "you")

    system_prompt = _build_chat_system_prompt(user_name)

    subprocess.run(["pbcopy"], input=system_prompt.encode(), check=True)
    webbrowser.open("https://claude.ai/new")

    click.echo("\n✦ Asterism context copied to clipboard.\n")
    click.echo("  In Claude:")
    click.echo("  1. Click the '+' button in the message box")
    click.echo("  2. Paste your graph context")
    click.echo("  3. Send it as your first message")
    click.echo("  4. Claude now knows who you are.\n")
    click.echo("  Tip: Start with:")
    click.echo("  'This is my Asterism knowledge graph.")
    click.echo("  Use it as context for all my questions.'\n")


@cli.command()
def view():
    """Open the constellation graph in your browser."""
    if not is_configured():
        click.echo("Run asterism init first.")
        sys.exit(1)
    from render import render_graph
    html_path = render_graph()
    webbrowser.open(f"file://{html_path}")


@cli.command()
@click.option("--source", type=click.Choice(["claude"]), required=True, help="Export source type.")
@click.option("--path", required=True, help="Path to the export file (conversations.json).")
def crawl(source, path):
    """Import a conversation export into the knowledge graph."""
    if not is_configured():
        click.echo("Run asterism init first.")
        sys.exit(1)
    from crawler import crawl_claude
    if source == "claude":
        crawl_claude(path)


if __name__ == "__main__":
    cli()
