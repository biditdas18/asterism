import os
from pyvis.network import Network
from graph import build_graph

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "asterism_graph.html")


def _weight_to_color(weight: float) -> str:
    # low weight -> dim purple (#4a1a6e), high weight -> white (#ffffff)
    t = min(max(weight / 5.0, 0.0), 1.0)
    r = int(0x4a + (0xff - 0x4a) * t)
    g = int(0x1a + (0xff - 0x1a) * t)
    b = int(0x6e + (0xff - 0x6e) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def render_graph() -> str:
    G = build_graph()

    net = Network(
        height="600px",
        width="100%",
        bgcolor="#0a0f1a",
        font_color="#cccccc",
        directed=True,
    )
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=120)

    for label, data in G.nodes(data=True):
        weight = data.get("weight", 1.0)
        size = 10 + weight * 6
        color = _weight_to_color(weight)
        net.add_node(label, label=label, size=size, color=color, title=f"{label}\nweight: {round(weight, 2)}")

    for src, tgt, data in G.edges(data=True):
        weight = data.get("weight", 1.0)
        net.add_edge(src, tgt, width=max(1.0, weight), title=f"weight: {round(weight, 2)}")

    net.save_graph(OUTPUT_PATH)

    # pyvis doesn't apply bgcolor to the HTML body — patch it in
    with open(OUTPUT_PATH, "r") as f:
        html = f.read()
    html = html.replace(
        "<body>",
        '<body style="background-color:#0a0f1a;margin:0;border:none;">',
        1,
    )
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)

    return OUTPUT_PATH
