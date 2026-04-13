#!/usr/bin/env python3
"""Compute differentiable graph layouts for benchmark dashboard visualization.

Implements force-directed layout using gradient descent optimization,
suitable for visualizing benchmark scenario relationships and dependencies.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import numpy as np  # type: ignore

    HAS_NP = True
except ImportError:
    HAS_NP = False


def fruchterman_reingold(
    adj: list[list[int]],
    n_iter: int = 100,
    k: float | None = None,
    seed: int = 42,
) -> list[tuple[float, float]]:
    """Compute Fruchterman-Reingold force-directed layout.

    Uses gradient descent with attraction/repulsion forces.
    Differentiable in the sense that positions are iteratively optimized.

    Args:
        adj: Adjacency matrix (n x n)
        n_iter: Number of iterations
        k: Optimal distance between nodes (None = sqrt(1/n))
        seed: Random seed for initial positions

    Returns:
        List of (x, y) positions for each node
    """
    n = len(adj)
    if n == 0:
        return []
    if n == 1:
        return [(0.5, 0.5)]

    rng = np.random.default_rng(seed)
    # Initialize positions randomly in unit square
    pos = rng.random((n, 2))

    # Optimal distance
    k_opt = k if k is not None else math.sqrt(1.0 / n)

    # Temperature (cooling schedule)
    t = 0.1
    dt = t / (n_iter + 1)

    for _ in range(n_iter):
        # Compute displacement for each node
        disp = np.zeros((n, 2))

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                delta = pos[i] - pos[j]
                dist = np.linalg.norm(delta)
                if dist < 1e-6:
                    dist = 1e-6
                    delta = rng.random(2) * 1e-4

                # Repulsive force (all pairs)
                repulsion = (k_opt * k_opt / dist) * (delta / dist)
                disp[i] += repulsion

                # Attractive force (edges only)
                if adj[i][j] or adj[j][i]:
                    attraction = (dist * dist / k_opt) * (delta / dist)
                    disp[i] -= attraction

        # Apply displacement with temperature limit
        for i in range(n):
            disp_norm = np.linalg.norm(disp[i])
            if disp_norm > 0:
                pos[i] += (disp[i] / disp_norm) * min(disp_norm, t)

        # Cool down
        t -= dt

        # Keep within bounds [0, 1]
        pos = np.clip(pos, 0.01, 0.99)

    return [(float(pos[i, 0]), float(pos[i, 1])) for i in range(n)]


def spring_layout(
    adj: list[list[int]],
    n_iter: int = 50,
    spring_constant: float = 1.0,
    repulsion_constant: float = 1.0,
    seed: int = 42,
) -> list[tuple[float, float]]:
    """Simple spring-based layout with Hooke's law.

    Args:
        adj: Adjacency matrix
        n_iter: Number of gradient descent steps
        spring_constant: Strength of edge attraction
        repulsion_constant: Strength of node repulsion
        seed: Random seed

    Returns:
        List of (x, y) positions
    """
    n = len(adj)
    if n == 0:
        return []
    if n == 1:
        return [(0.5, 0.5)]

    rng = np.random.default_rng(seed)
    pos = rng.random((n, 2))

    learning_rate = 0.1

    for _ in range(n_iter):
        grad = np.zeros((n, 2))

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                delta = pos[i] - pos[j]
                dist = np.linalg.norm(delta)
                if dist < 1e-6:
                    continue

                # Repulsion: gradient of 1/dist
                grad[i] += repulsion_constant * delta / (dist ** 3)

                # Attraction (edges): gradient of dist^2
                if adj[i][j] or adj[j][i]:
                    grad[i] -= spring_constant * delta

        # Gradient descent step
        pos -= learning_rate * grad
        pos = np.clip(pos, 0.01, 0.99)

        # Decay learning rate
        learning_rate *= 0.95

    return [(float(pos[i, 0]), float(pos[i, 1])) for i in range(n)]


def hierarchical_layout(
    adj: list[list[int]],
    layers: list[list[int]] | None = None,
) -> list[tuple[float, float]]:
    """Layered hierarchical layout (Sugiyama-style).

    If layers aren't provided, computes BFS layers from first node.

    Args:
        adj: Adjacency matrix
        layers: Pre-computed layer assignment

    Returns:
        List of (x, y) positions
    """
    n = len(adj)
    if n == 0:
        return []
    if n == 1:
        return [(0.5, 0.5)]

    if layers is None:
        # BFS layering
        layers = []
        visited = set()
        current = {0}
        while current:
            layer = list(current)
            layers.append(layer)
            visited.update(current)
            next_layer = set()
            for node in current:
                for j in range(n):
                    if adj[node][j] and j not in visited:
                        next_layer.add(j)
            current = next_layer

        # Add any unvisited nodes to last layer
        unvisited = set(range(n)) - visited
        if unvisited:
            layers.append(list(unvisited))

    positions = [(0.0, 0.0)] * n
    num_layers = len(layers)

    for layer_idx, layer in enumerate(layers):
        y = (layer_idx + 0.5) / num_layers if num_layers > 1 else 0.5
        for pos_in_layer, node in enumerate(layer):
            x = (pos_in_layer + 0.5) / len(layer) if len(layer) > 1 else 0.5
            positions[node] = (x, y)

    return positions


def compute_layout_metrics(
    pos: list[tuple[float, float]],
    adj: list[list[int]],
) -> dict[str, float]:
    """Compute layout quality metrics.

    Args:
        pos: Node positions
        adj: Adjacency matrix

    Returns:
        Dictionary of metrics
    """
    n = len(pos)
    if n < 2:
        return {
            "edge_crossing_estimate": 0.0,
            "mean_edge_length": 0.0,
            "edge_length_variance": 0.0,
            "node_distribution_spread": 0.0,
        }

    # Edge lengths
    edge_lengths = []
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i][j] or adj[j][i]:
                dx = pos[i][0] - pos[j][0]
                dy = pos[i][1] - pos[j][1]
                edge_lengths.append(math.sqrt(dx * dx + dy * dy))

    mean_edge = sum(edge_lengths) / len(edge_lengths) if edge_lengths else 0.0
    var_edge = (
        sum((e - mean_edge) ** 2 for e in edge_lengths) / len(edge_lengths)
        if edge_lengths
        else 0.0
    )

    # Node distribution spread (standard deviation of positions)
    mean_x = sum(p[0] for p in pos) / n
    mean_y = sum(p[1] for p in pos) / n
    spread = math.sqrt(
        sum((p[0] - mean_x) ** 2 + (p[1] - mean_y) ** 2 for p in pos) / n
    )

    # Edge crossing estimate (sampling-based for large graphs)
    crossings = 0
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i][j] or adj[j][i]]
    sample_size = min(1000, len(edges) * (len(edges) - 1) // 2)
    if len(edges) > 1:
        rng = np.random.default_rng(42)
        for _ in range(sample_size):
            e1_idx = rng.integers(0, len(edges))
            e2_idx = rng.integers(0, len(edges))
            if e1_idx == e2_idx:
                continue
            e1, e2 = edges[e1_idx], edges[e2_idx]
            if len(set(e1) & set(e2)) > 0:
                continue  # Shared vertex
            # Check intersection
            if segments_intersect(pos[e1[0]], pos[e1[1]], pos[e2[0]], pos[e2[1]]):
                crossings += 1
        crossing_rate = crossings / sample_size if sample_size > 0 else 0.0
    else:
        crossing_rate = 0.0

    return {
        "edge_crossing_estimate": round(crossing_rate, 6),
        "mean_edge_length": round(mean_edge, 6),
        "edge_length_variance": round(var_edge, 6),
        "node_distribution_spread": round(spread, 6),
    }


def segments_intersect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> bool:
    """Check if line segments (p1,p2) and (p3,p4) intersect."""

    def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fingerprints",
        default="artifacts/conformance/graph_fingerprints_v1.json",
        help="Input fingerprints file",
    )
    parser.add_argument(
        "--output",
        default="artifacts/conformance/benchmark_layout_v1.json",
        help="Output layout file",
    )
    parser.add_argument(
        "--algorithm",
        choices=["fruchterman_reingold", "spring", "hierarchical"],
        default="fruchterman_reingold",
        help="Layout algorithm",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of optimization iterations",
    )
    parser.add_argument("--demo", action="store_true", help="Generate demo layout")
    args = parser.parse_args()

    if not HAS_NP:
        raise SystemExit("numpy is required: pip install numpy")

    nodes: list[str] = []
    adj: list[list[int]] = []

    if args.demo:
        # Demo: create a small benchmark graph
        nodes = [
            "shortest_path",
            "components",
            "centrality",
            "flow",
            "io_roundtrip",
            "mutation_cycle",
            "bfs_baseline",
            "dijkstra",
            "bellman_ford",
        ]
        n = len(nodes)
        adj = [[0] * n for _ in range(n)]
        # Connect related benchmarks
        edges = [
            (0, 6),  # shortest_path -> bfs_baseline
            (0, 7),  # shortest_path -> dijkstra
            (0, 8),  # shortest_path -> bellman_ford
            (1, 6),  # components -> bfs_baseline
            (2, 7),  # centrality -> dijkstra
            (3, 7),  # flow -> dijkstra
            (7, 8),  # dijkstra -> bellman_ford
        ]
        for i, j in edges:
            adj[i][j] = 1
            adj[j][i] = 1
        print(f"Demo: {n} nodes, {len(edges)} edges")
    else:
        fingerprints_path = Path(args.fingerprints)
        if not fingerprints_path.exists():
            raise SystemExit(f"missing fingerprints file: {fingerprints_path}")

        data = json.loads(fingerprints_path.read_text(encoding="utf-8"))
        fingerprints = data.get("fingerprints", [])
        clusters = data.get("clusters", [])

        # Build graph from clusters (nodes in same cluster are connected)
        node_to_idx = {}
        for fp in fingerprints:
            path = fp.get("fixture_path", "")
            node_to_idx[path] = len(nodes)
            nodes.append(path)

        n = len(nodes)
        adj = [[0] * n for _ in range(n)]

        for cluster in clusters:
            members = cluster.get("members", [])
            for i, m1 in enumerate(members):
                for m2 in members[i + 1 :]:
                    if m1 in node_to_idx and m2 in node_to_idx:
                        idx1, idx2 = node_to_idx[m1], node_to_idx[m2]
                        adj[idx1][idx2] = 1
                        adj[idx2][idx1] = 1

        print(f"Loaded {n} nodes from fingerprints")

    # Compute layout
    print(f"Computing {args.algorithm} layout with {args.iterations} iterations...")
    if args.algorithm == "fruchterman_reingold":
        positions = fruchterman_reingold(adj, n_iter=args.iterations)
    elif args.algorithm == "spring":
        positions = spring_layout(adj, n_iter=args.iterations)
    else:
        positions = hierarchical_layout(adj)

    # Compute metrics
    metrics = compute_layout_metrics(positions, adj)
    print(f"Layout metrics: crossing_rate={metrics['edge_crossing_estimate']:.4f}, "
          f"spread={metrics['node_distribution_spread']:.4f}")

    # Build output
    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "algorithm": args.algorithm,
        "iterations": args.iterations,
        "node_count": len(nodes),
        "edge_count": sum(sum(row) for row in adj) // 2,
        "metrics": metrics,
        "nodes": [
            {"id": nodes[i], "x": round(positions[i][0], 6), "y": round(positions[i][1], 6)}
            for i in range(len(nodes))
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"benchmark_layout:{output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
