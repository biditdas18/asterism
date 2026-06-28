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


@cli.command()
def chat():
    """Launch the Asterism chat interface."""
    if not is_configured():
        click.echo("Run asterism init first.")
        sys.exit(1)
    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    streamlit = os.path.join(os.path.dirname(sys.executable), "streamlit")
    subprocess.run([streamlit, "run", app_path])


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
    from crawler import crawl_claude
    if source == "claude":
        crawl_claude(path)


if __name__ == "__main__":
    cli()
