import argparse
import math
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from adjustText import adjust_text
from matplotlib.colors import to_rgba
from matplotlib.patches import FancyBboxPatch, Polygon

try:
    from community import community_louvain
except ImportError as exc:
    raise ImportError(
        "The python-louvain package is required. Install dependencies with: "
        "pip install -r requirements.txt"
    ) from exc

try:
    from scipy.spatial import ConvexHull
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False

warnings.filterwarnings("ignore")

FIG_W = 14.32
FIG_H = 5.8
DPI = 300
FSIZE = 9.5
BG = "#F8F7F3"
FG = "#111111"
GAP = 0.20
PALETTE = [
    "#1F6FAE",
    "#C0392B",
    "#E67E22",
    "#27AE60",
    "#7D3C98",
    "#117A65",
    "#B7950B",
    "#6E2F20",
]
ALIASES = {
    "Rakuten Mobile": "Rakuten Symphony",
    "Rakuten mobile": "Rakuten Symphony",
    "Rakuten": "Rakuten Symphony",
}
BAD_VALUES = {"", "nan", "none", "n/a", "-", "—", "–", "?"}


def clean_value(value):
    text = str(value).strip() if value is not None else ""
    return None if text.lower() in BAD_VALUES else text


def load_edges(csv_path):
    raw = pd.read_csv(csv_path)
    required = {"CompanyA", "CompanyB", "Weight"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {sorted(missing)}")

    for column in ["CompanyA", "CompanyB"]:
        raw[column] = raw[column].apply(clean_value)

    raw = raw.dropna(subset=["CompanyA", "CompanyB", "Weight"])

    for column in ["CompanyA", "CompanyB"]:
        raw[column] = raw[column].astype(str).str.strip().replace(ALIASES)

    raw["Weight"] = pd.to_numeric(raw["Weight"], errors="coerce").fillna(0)
    edges = raw[(raw["Weight"] > 0) & (raw["CompanyA"] != raw["CompanyB"])].copy()
    edges["pair"] = edges.apply(lambda row: tuple(sorted([row.CompanyA, row.CompanyB])), axis=1)
    edges = edges.groupby("pair", as_index=False).agg(Weight=("Weight", "sum"))
    edges[["CompanyA", "CompanyB"]] = pd.DataFrame(edges["pair"].tolist(), index=edges.index)
    return edges[["CompanyA", "CompanyB", "Weight"]]


def build_graph(edges):
    graph = nx.Graph()
    for _, row in edges.iterrows():
        graph.add_edge(row.CompanyA, row.CompanyB, weight=float(row.Weight))
    keep = [node for component in nx.connected_components(graph) if len(component) >= 2 for node in component]
    return graph.subgraph(keep).copy()


def node_strengths(graph):
    return {
        node: sum(data.get("weight", 1) for _, _, data in graph.edges(node, data=True))
        for node in graph.nodes()
    }


def component_layout(component):
    try:
        positions = nx.kamada_kawai_layout(component, weight="weight")
    except Exception:
        positions = nx.spring_layout(component, seed=42, k=1.8 / math.sqrt(max(len(component), 1)))

    coordinates = np.array(list(positions.values()))
    lower = coordinates.min(0)
    upper = coordinates.max(0)
    span = np.where(upper - lower < 1e-9, 1.0, upper - lower)
    return {node: (value - lower) / span for node, value in positions.items()}


def packed_layout(graph):
    components = sorted(
        [graph.subgraph(component).copy() for component in nx.connected_components(graph)],
        key=len,
        reverse=True,
    )
    widths = [math.sqrt(len(component)) for component in components]
    total_width = sum(widths) + GAP * (len(components) - 1)
    positions = {}
    cursor = 0.0

    for component, width in zip(components, widths):
        slot = width / total_width
        local_positions = component_layout(component)
        for node, point in local_positions.items():
            positions[node] = (cursor + float(point[0]) * slot, float(point[1]))
        cursor += slot + GAP / total_width

    coordinates = np.array(list(positions.values()))
    lower = coordinates.min(0)
    upper = coordinates.max(0)
    span = np.where(upper - lower < 1e-9, 1.0, upper - lower)
    return {
        node: (float((value[0] - lower[0]) / span[0]), float((value[1] - lower[1]) / span[1]))
        for node, value in positions.items()
    }


def scaled_node_sizes(graph, strengths):
    values = np.array([strengths[node] for node in graph.nodes()])
    lower = values.min()
    upper = values.max()
    return {
        node: 120 + 1100 * ((strengths[node] - lower) / (upper - lower + 1e-9)) ** 0.65
        for node in graph.nodes()
    }


def node_radius(node, sizes):
    return math.sqrt(sizes[node]) / 2 * (1.0 / (FIG_W * 72)) * 1.25


def label_positions(positions, partition, sizes):
    centroids = {}
    for community in set(partition.values()):
        members = [node for node, assigned in partition.items() if assigned == community]
        centroids[community] = (
            np.mean([positions[node][0] for node in members]),
            np.mean([positions[node][1] for node in members]),
        )

    labels = {}
    for node in positions:
        x, y = positions[node]
        cx, cy = centroids[partition[node]]
        dx = x - cx
        dy = y - cy
        distance = math.sqrt(dx * dx + dy * dy)
        offset = node_radius(node, sizes) + 0.018
        if distance < 1e-4:
            labels[node] = (x, y + offset)
        else:
            labels[node] = (x + dx / distance * offset, y + dy / distance * offset)
    return labels


def text_alignment(node, positions, labels):
    x, y = positions[node]
    lx, ly = labels[node]
    dx = lx - x
    if dx > 0.005:
        return "left", "center"
    if dx < -0.005:
        return "right", "center"
    if ly > y:
        return "center", "bottom"
    return "center", "top"


def draw_hulls(axis, positions, partition, colors, pad=0.04, alpha=0.17):
    communities = {}
    for node, community in partition.items():
        communities.setdefault(community, []).append(node)

    for community, nodes in communities.items():
        points = np.array([positions[node] for node in nodes])
        color = colors[community]
        face = (*to_rgba(color)[:3], alpha)
        edge = (*to_rgba(color)[:3], 0.48)

        if HAVE_SCIPY and len(points) >= 3:
            try:
                hull = ConvexHull(points)
                hull_points = points[hull.vertices]
                center = hull_points.mean(0)
                expanded = center + (hull_points - center) * (1 + pad)
                axis.add_patch(
                    Polygon(expanded, closed=True, facecolor=face, edgecolor=edge, linewidth=0.9, zorder=0)
                )
                continue
            except Exception:
                pass

        x_min, y_min = points.min(0)
        x_max, y_max = points.max(0)
        dx = x_max - x_min
        dy = y_max - y_min
        x_pad = max(pad * (dx or 0.05), 0.015)
        y_pad = max(pad * (dy or 0.05), 0.015)
        axis.add_patch(
            FancyBboxPatch(
                (x_min - x_pad, y_min - y_pad),
                max(dx + 2 * x_pad, 0.03),
                max(dy + 2 * y_pad, 0.03),
                boxstyle="round,pad=0.005",
                linewidth=0.9,
                edgecolor=edge,
                facecolor=face,
                zorder=0,
            )
        )


def plot_network(graph, output_path):
    strengths = node_strengths(graph)
    partition = community_louvain.best_partition(graph, weight="weight", resolution=1.5, random_state=42)
    communities = sorted(set(partition.values()))
    colors = {community: PALETTE[index % len(PALETTE)] for index, community in enumerate(communities)}
    positions = packed_layout(graph)
    sizes = scaled_node_sizes(graph, strengths)
    labels = label_positions(positions, partition, sizes)
    x_values = [value[0] for value in positions.values()]
    y_values = [value[1] for value in positions.values()]

    figure, axis = plt.subplots(figsize=(FIG_W, FIG_H), facecolor=BG)
    axis.set_facecolor(BG)
    axis.set_xlim(min(x_values) - 0.05, max(x_values) + 0.05)
    axis.set_ylim(min(y_values) - 0.22, max(y_values) + 0.06)

    draw_hulls(axis, positions, partition, colors, pad=0.055, alpha=0.18)

    max_weight = max(data["weight"] for _, _, data in graph.edges(data=True))
    for source, target, data in graph.edges(data=True):
        weight = data["weight"]
        axis.plot(
            [positions[source][0], positions[target][0]],
            [positions[source][1], positions[target][1]],
            color=colors[partition[source]],
            alpha=0.12 + 0.38 * (weight / max_weight),
            lw=0.40 + 0.90 * (weight / max_weight) ** 0.55,
            solid_capstyle="round",
            zorder=1,
        )

    for node in graph.nodes():
        x, y = positions[node]
        axis.scatter(x, y, s=sizes[node] * 1.65, c="white", alpha=0.70, zorder=2, linewidths=0)
        axis.scatter(
            x,
            y,
            s=sizes[node],
            c=colors[partition[node]],
            alpha=0.93,
            edgecolors="white",
            linewidths=0.7,
            zorder=3,
        )

    text_objects = []
    for node in graph.nodes():
        lx, ly = labels[node]
        horizontal, vertical = text_alignment(node, positions, labels)
        text = axis.text(
            lx,
            ly,
            node,
            fontsize=FSIZE,
            fontfamily="DejaVu Sans",
            fontweight="bold",
            color=FG,
            ha=horizontal,
            va=vertical,
            zorder=6,
            clip_on=False,
        )
        text.set_path_effects([pe.Stroke(linewidth=2.3, foreground=BG, alpha=0.96), pe.Normal()])
        text_objects.append(text)

    adjust_text(
        text_objects,
        x=[positions[node][0] for node in graph.nodes()],
        y=[positions[node][1] for node in graph.nodes()],
        expand=(1.15, 1.35),
        force_text=(0.20, 0.45),
        force_points=(0.15, 0.30),
        arrowprops={
            "arrowstyle": "-",
            "color": "#CCCCCC",
            "lw": 0.40,
            "alpha": 0.55,
            "shrinkA": 7,
            "shrinkB": 2,
        },
        min_arrow_len=8,
        avoid_self=True,
        only_move={"points": "y", "text": "xy", "objects": "xy"},
        iterations=600,
        ax=axis,
    )

    for text in text_objects:
        text.set_path_effects([pe.Stroke(linewidth=2.3, foreground=BG, alpha=0.96), pe.Normal()])

    community_sizes = {}
    for _, community in partition.items():
        community_sizes[community] = community_sizes.get(community, 0) + 1

    handles = [
        mpatches.Patch(
            facecolor=colors[community],
            edgecolor="#444444",
            linewidth=0.5,
            label=f"Cluster {community + 1} (n={community_sizes[community]})",
        )
        for community in sorted(community_sizes, key=lambda item: -community_sizes[item])
    ]

    legend = axis.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=len(handles),
        fontsize=FSIZE - 0.5,
        title="Communities identified by Louvain community detection",
        title_fontsize=FSIZE - 0.5,
        framealpha=0.97,
        facecolor="white",
        edgecolor="#CCCCCC",
        handlelength=1.2,
        handleheight=1.0,
        borderpad=0.70,
        labelspacing=0.45,
        columnspacing=0.90,
    )
    legend.get_title().set_fontweight("bold")
    legend.get_title().set_color(FG)
    for label in legend.get_texts():
        label.set_color(FG)

    axis.set_axis_off()
    plt.tight_layout(pad=0.25)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(figure)
    return partition


def main():
    parser = argparse.ArgumentParser(description="Generate the Open RAN co-occurrence network figure.")
    parser.add_argument("--input", default="data/openran_company_edges.csv", help="Path to the edge-list CSV file.")
    parser.add_argument("--output", default="outputs/pilots.png", help="Path for the generated PNG figure.")
    args = parser.parse_args()

    edges = load_edges(Path(args.input))
    graph = build_graph(edges)
    partition = plot_network(graph, Path(args.output))
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Communities: {len(set(partition.values()))}")
    print(f"Saved figure: {args.output}")


if __name__ == "__main__":
    main()
