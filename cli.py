import os
import sys
# ensure the project root is on sys.path when invoked via installed script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subprocess
import webbrowser
import click
from config import load_config, save_config, is_configured, get_db_path, CONFIG_DIR


@click.group()
def cli():
    """✦ Asterism — an X-ray of your brain."""


@cli.command()
def init():
    """Set up Asterism for the first time."""
    click.echo("\n✦ Welcome to Asterism — an X-ray of your brain.\n")

    api_key = click.prompt("Anthropic API key", hide_input=True)
    if not api_key.strip():
        click.echo("API key cannot be empty.")
        sys.exit(1)

    click.echo("\nHow should Asterism extract knowledge?")
    click.echo("  1. Local (free, private) — uses Ollama + llama3.2:3b (~2GB download)")
    click.echo("  2. Cloud (fast, ~$0.001/msg) — uses Anthropic Haiku\n")
    choice = click.prompt("Choice", type=click.Choice(["1", "2"]), default="2")

    config = load_config()
    config["anthropic_api_key"] = api_key.strip()

    if choice == "1":
        config["extractor_mode"] = "local"
        # check ollama
        result = subprocess.run(["ollama", "--version"], capture_output=True)
        if result.returncode != 0:
            click.echo("\nOllama not found. Installing...")
            platform = sys.platform
            if platform in ("darwin", "linux"):
                subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
            else:
                click.echo("Windows: download Ollama manually from https://ollama.com/download")
                click.echo("Then re-run: asterism init")
                sys.exit(1)
        click.echo("\nPulling llama3.2:3b (this may take a few minutes)...")
        subprocess.run(["ollama", "pull", "llama3.2:3b"], check=True)
    else:
        config["extractor_mode"] = "haiku"

    os.makedirs(CONFIG_DIR, exist_ok=True)

    # init DB at ~/.asterism/asterism.db
    import db as _db
    _db.DB_PATH = get_db_path()
    _db.init_db()

    save_config(config)
    click.echo("\n✓ Ready. Run: asterism chat\n")


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
