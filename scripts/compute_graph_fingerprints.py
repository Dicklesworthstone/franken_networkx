#!/usr/bin/env python3
"""Compute topological graph fingerprints for fixture clustering.

Uses graph-theoretic invariants as a simplified persistent homology approach:
- H0 (connected components): number and size distribution
- H1 (cycles): cycle basis dimension and structure
- Degree distribution moments
- Spectral signature (Laplacian eigenvalues)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import networkx as nx  # type: ignore

    HAS_NX = True
except ImportError:
    HAS_NX = False


def degree_moments(degrees: list[int]) -> dict[str, float]:
    """Compute statistical moments of degree sequence."""
    if not degrees:
        return {"mean": 0.0, "variance": 0.0, "skewness": 0.0, "kurtosis": 0.0, "max": 0}

    n = len(degrees)
    mean = sum(degrees) / n
    variance = sum((d - mean) ** 2 for d in degrees) / n if n > 1 else 0.0
    std = math.sqrt(variance) if variance > 0 else 1.0

    skewness = 0.0
    kurtosis = 0.0
    if std > 0 and n > 2:
        skewness = sum((d - mean) ** 3 for d in degrees) / (n * std**3)
    if std > 0 and n > 3:
        kurtosis = sum((d - mean) ** 4 for d in degrees) / (n * std**4) - 3.0

    return {
        "mean": round(mean, 6),
        "variance": round(variance, 6),
        "skewness": round(skewness, 6),
        "kurtosis": round(kurtosis, 6),
        "max": max(degrees),
    }


def coerce_node_id(node: Any) -> str:
    """Normalize node identifiers to stable string keys."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        for key in ("id", "name", "label"):
            if key in node and node[key] is not None:
                return str(node[key])
        return str(node)
    return str(node)


def safe_json_loads(payload: str) -> Any | None:
    """Parse JSON payload, returning None on decode errors."""
    try:
        return json.loads(payload)  # ubs:ignore — safe_json_loads handles JSON errors here
    except json.JSONDecodeError:
        return None


def compute_h0_fingerprint(g: "nx.Graph") -> dict[str, Any]:
    """Compute H0 (connected components) fingerprint."""
    components = list(nx.connected_components(g))
    sizes = sorted([len(c) for c in components], reverse=True)

    return {
        "component_count": len(components),
        "largest_component_size": sizes[0] if sizes else 0,
        "second_largest_size": sizes[1] if len(sizes) > 1 else 0,
        "singleton_count": sum(1 for s in sizes if s == 1),
        "size_gini": gini_coefficient(sizes) if sizes else 0.0,
    }


def compute_h1_fingerprint(g: "nx.Graph") -> dict[str, Any]:
    """Compute H1 (cycle) fingerprint using cycle basis."""
    try:
        cycles = nx.cycle_basis(g)
        cycle_lengths = [len(c) for c in cycles]

        return {
            "cycle_count": len(cycles),
            "min_cycle_length": min(cycle_lengths) if cycle_lengths else 0,
            "max_cycle_length": max(cycle_lengths) if cycle_lengths else 0,
            "mean_cycle_length": round(sum(cycle_lengths) / len(cycle_lengths), 2)
            if cycle_lengths
            else 0.0,
            "betti_1": len(cycles),  # H1 dimension = |E| - |V| + |CC|
        }
    except Exception:
        return {
            "cycle_count": 0,
            "min_cycle_length": 0,
            "max_cycle_length": 0,
            "mean_cycle_length": 0.0,
            "betti_1": 0,
        }


def compute_spectral_fingerprint(g: "nx.Graph", k: int = 5) -> dict[str, Any]:
    """Compute spectral fingerprint from Laplacian eigenvalues."""
    if g.number_of_nodes() == 0:
        return {"eigenvalues": [], "algebraic_connectivity": 0.0, "spectral_radius": 0.0}

    try:
        # Use normalized Laplacian for size-invariance
        L = nx.normalized_laplacian_matrix(g)
        # Compute a few smallest eigenvalues
        import numpy as np  # type: ignore

        eigenvalues = np.linalg.eigvalsh(L.toarray())
        eigenvalues = sorted(eigenvalues)[:k]

        algebraic_connectivity = eigenvalues[1] if len(eigenvalues) > 1 else 0.0

        return {
            "eigenvalues": [round(float(e), 6) for e in eigenvalues],
            "algebraic_connectivity": round(float(algebraic_connectivity), 6),
            "spectral_radius": round(float(max(eigenvalues)), 6) if eigenvalues else 0.0,
        }
    except Exception:
        return {"eigenvalues": [], "algebraic_connectivity": 0.0, "spectral_radius": 0.0}


def gini_coefficient(values: list[int]) -> float:
    """Compute Gini coefficient for inequality measure."""
    if not values or sum(values) == 0:
        return 0.0
    n = len(values)
    sorted_vals = sorted(values)
    cumulative = 0
    numerator = 0
    for i, v in enumerate(sorted_vals):
        cumulative += v
        numerator += (2 * (i + 1) - n - 1) * v
    return round(numerator / (n * cumulative), 6) if cumulative > 0 else 0.0


def fingerprint_hash(fp: dict[str, Any]) -> str:
    """Create a stable hash of the fingerprint."""
    canonical = json.dumps(fp, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def fingerprint_graph(g: "nx.Graph") -> dict[str, Any]:
    """Compute complete topological fingerprint for a graph."""
    degrees = [d for _, d in g.degree()]

    return {
        "node_count": g.number_of_nodes(),
        "edge_count": g.number_of_edges(),
        "density": round(nx.density(g), 6) if g.number_of_nodes() > 1 else 0.0,
        "degree_moments": degree_moments(degrees),
        "h0": compute_h0_fingerprint(g),
        "h1": compute_h1_fingerprint(g),
        "spectral": compute_spectral_fingerprint(g),
    }


def fingerprint_distance(fp1: dict[str, Any], fp2: dict[str, Any]) -> float:
    """Compute distance between two fingerprints."""
    distance = 0.0

    # Basic metrics
    distance += abs(fp1["node_count"] - fp2["node_count"]) / max(
        fp1["node_count"], fp2["node_count"], 1
    )
    distance += abs(fp1["edge_count"] - fp2["edge_count"]) / max(
        fp1["edge_count"], fp2["edge_count"], 1
    )
    distance += abs(fp1["density"] - fp2["density"])

    # Degree moments
    dm1, dm2 = fp1["degree_moments"], fp2["degree_moments"]
    for key in ["mean", "variance", "skewness"]:
        max_val = max(abs(dm1[key]), abs(dm2[key]), 1.0)
        distance += abs(dm1[key] - dm2[key]) / max_val

    # H0 metrics
    h0_1, h0_2 = fp1["h0"], fp2["h0"]
    distance += abs(h0_1["component_count"] - h0_2["component_count"]) / max(
        h0_1["component_count"], h0_2["component_count"], 1
    )
    distance += abs(h0_1["size_gini"] - h0_2["size_gini"])

    # H1 metrics
    h1_1, h1_2 = fp1["h1"], fp2["h1"]
    distance += abs(h1_1["betti_1"] - h1_2["betti_1"]) / max(
        h1_1["betti_1"], h1_2["betti_1"], 1
    )

    # Spectral (compare first few eigenvalues)
    spec1 = fp1["spectral"]["eigenvalues"]
    spec2 = fp2["spectral"]["eigenvalues"]
    min_len = min(len(spec1), len(spec2))
    for i in range(min_len):
        distance += abs(spec1[i] - spec2[i])

    return round(distance, 6)


def parse_embedded_graph(data: dict) -> "nx.Graph | None":
    """Parse graph from fixture operations (embedded JSON format)."""
    for op in data.get("operations", []):
        input_str = op.get("input", "")
        if not input_str or not isinstance(input_str, str):
            continue
        try:
            graph_data = safe_json_loads(input_str)
            if graph_data is None:
                continue
            if not isinstance(graph_data, dict):
                continue
            g = nx.Graph()
            # Handle node-link format
            for node in graph_data.get("nodes", []):
                node_id = coerce_node_id(node)
                g.add_node(node_id)
            for link in graph_data.get("links", graph_data.get("edges", [])):
                if isinstance(link, dict):
                    left = link.get("left")
                    right = link.get("right")
                    src = left if left is not None else link.get("source")
                    tgt = right if right is not None else link.get("target")
                    if src is not None and tgt is not None:
                        g.add_edge(coerce_node_id(src), coerce_node_id(tgt))
            if g.number_of_nodes() > 0:
                return g
        except json.JSONDecodeError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="crates/fnx-conformance/tests/fixtures",
        help="Directory containing fixture JSON files",
    )
    parser.add_argument(
        "--output",
        default="artifacts/conformance/graph_fingerprints_v1.json",
        help="Output fingerprint catalog",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate demo fingerprints for standard graph types",
    )
    args = parser.parse_args()

    if not HAS_NX:
        raise SystemExit("networkx is required: pip install networkx")

    fingerprints = []

    if args.demo:
        # Generate fingerprints for standard graph types
        demo_graphs = [
            ("path_10", nx.path_graph(10)),
            ("path_50", nx.path_graph(50)),
            ("cycle_10", nx.cycle_graph(10)),
            ("cycle_50", nx.cycle_graph(50)),
            ("complete_5", nx.complete_graph(5)),
            ("complete_10", nx.complete_graph(10)),
            ("star_10", nx.star_graph(10)),
            ("star_50", nx.star_graph(50)),
            ("grid_4x4", nx.grid_2d_graph(4, 4)),
            ("grid_8x8", nx.grid_2d_graph(8, 8)),
            ("petersen", nx.petersen_graph()),
            ("karate", nx.karate_club_graph()),
            ("erdos_renyi_50_01", nx.erdos_renyi_graph(50, 0.1, seed=42)),
            ("erdos_renyi_50_02", nx.erdos_renyi_graph(50, 0.2, seed=42)),
            ("barabasi_albert_50_2", nx.barabasi_albert_graph(50, 2, seed=42)),
            ("watts_strogatz_50", nx.watts_strogatz_graph(50, 4, 0.3, seed=42)),
        ]
        print("Generating demo fingerprints...")
        for name, g in demo_graphs:
            fp = fingerprint_graph(g)
            fp["fixture_path"] = f"demo/{name}"
            fp["fingerprint_hash"] = fingerprint_hash(fp)
            fingerprints.append(fp)
            print(f"  {name}: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    else:
        fixtures_dir = Path(args.fixtures)
        if not fixtures_dir.exists():
            raise SystemExit(f"missing fixtures directory: {fixtures_dir}")

        print(f"Processing fixtures in {fixtures_dir}...")

        for path in sorted(fixtures_dir.rglob("*.json")):
            try:
                data = safe_json_loads(path.read_text(encoding="utf-8"))
                if data is None or not isinstance(data, dict):
                    continue

                # Try direct graph data
                graph_data = data.get("graph") or data.get("input_graph")
                g = None

                if graph_data and isinstance(graph_data, dict):
                    g = nx.Graph()
                    for node in graph_data.get("nodes", []):
                        node_id = coerce_node_id(node)
                        g.add_node(node_id)
                    for edge in graph_data.get("edges", []):
                        if isinstance(edge, dict):
                            left = edge.get("left")
                            right = edge.get("right")
                            src = left if left is not None else edge.get("source")
                            tgt = right if right is not None else edge.get("target")
                            if src is not None and tgt is not None:
                                g.add_edge(
                                    coerce_node_id(src),
                                    coerce_node_id(tgt),
                                )
                        elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
                            g.add_edge(coerce_node_id(edge[0]), coerce_node_id(edge[1]))
                else:
                    # Try embedded JSON format
                    g = parse_embedded_graph(data)

                if g is None or g.number_of_nodes() == 0:
                    continue

                fp = fingerprint_graph(g)
                fp["fixture_path"] = str(path.relative_to(fixtures_dir))
                fp["fingerprint_hash"] = fingerprint_hash(fp)
                fingerprints.append(fp)

            except (KeyError, TypeError, ValueError) as e:
                print(f"  skipping {path.name}: {e}")
                continue

    print(f"Computed {len(fingerprints)} fingerprints")

    # Cluster by similarity (simple threshold-based)
    clusters: list[list[int]] = []
    assigned = set()
    threshold = 2.0  # Distance threshold for same cluster

    for i, fp1 in enumerate(fingerprints):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j, fp2 in enumerate(fingerprints):
            if j <= i or j in assigned:
                continue
            dist = fingerprint_distance(fp1, fp2)
            if dist < threshold:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)

    fixtures_path = "demo" if args.demo else str(args.fixtures)
    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixtures_path": fixtures_path,
        "fingerprint_count": len(fingerprints),
        "cluster_count": len(clusters),
        "clustering_threshold": threshold,
        "fingerprints": fingerprints,
        "clusters": [
            {
                "cluster_id": idx,
                "size": len(members),
                "members": [fingerprints[m]["fixture_path"] for m in members],
            }
            for idx, members in enumerate(clusters)
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"graph_fingerprints:{output_path}")
    print(f"clusters: {len(clusters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
