#!/usr/bin/env python3
"""Compute fixture diversity using Wasserstein distance on graph spectra.

Uses optimal transport (earth mover's distance) to measure spectral similarity
between graphs, enabling diversity-based fixture selection for testing.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import networkx as nx  # type: ignore
    import numpy as np  # type: ignore

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


def laplacian_spectrum(g: "nx.Graph", k: int = 20) -> list[float]:
    """Compute normalized Laplacian spectrum (first k eigenvalues)."""
    if g.number_of_nodes() == 0:
        return []
    try:
        L = nx.normalized_laplacian_matrix(g)
        eigenvalues = np.linalg.eigvalsh(L.toarray())
        return sorted(eigenvalues)[:min(k, len(eigenvalues))]
    except Exception:
        return []


def safe_json_loads(payload: str) -> Any | None:
    """Parse JSON payload, returning None on decode errors."""
    try:
        return json.loads(payload)  # ubs:ignore — safe_json_loads handles JSON errors here
    except json.JSONDecodeError:
        return None


def wasserstein_1d(a: list[float], b: list[float]) -> float:
    """Compute 1D Wasserstein distance between two sorted sequences.

    For 1D distributions, W1 = sum(|CDF_a(x) - CDF_b(x)|) integrated over x.
    For sorted samples of equal length, this equals mean(|a_i - b_i|).
    """
    if not a or not b:
        return float("inf") if (a or b) else 0.0

    # Pad shorter sequence with zeros at the front to preserve sorted order.
    # Eigenvalues are non-negative, so zeros belong at the start.
    max_len = max(len(a), len(b))
    a_sorted = sorted(a)
    b_sorted = sorted(b)
    a_padded = [0.0] * (max_len - len(a_sorted)) + a_sorted
    b_padded = [0.0] * (max_len - len(b_sorted)) + b_sorted

    return sum(abs(ai - bi) for ai, bi in zip(a_padded, b_padded)) / max_len


def spectral_diversity_matrix(
    spectra: list[tuple[str, list[float]]],
) -> dict[str, dict[str, float]]:
    """Compute pairwise Wasserstein distances between spectra."""
    n = len(spectra)
    matrix: dict[str, dict[str, float]] = {}

    for i, (name_i, spec_i) in enumerate(spectra):
        row: dict[str, float] = {}
        for j, (name_j, spec_j) in enumerate(spectra):
            if i == j:
                row[name_j] = 0.0
            elif i > j:
                # Use already computed value (symmetric)
                row[name_j] = matrix[name_j][name_i]
            else:
                row[name_j] = round(wasserstein_1d(spec_i, spec_j), 6)
        matrix[name_i] = row

    return matrix


def greedy_diverse_selection(
    spectra: list[tuple[str, list[float]]],
    k: int,
    matrix: dict[str, dict[str, float]],
) -> list[str]:
    """Select k most diverse fixtures using greedy max-min distance."""
    if len(spectra) <= k:
        return [name for name, _ in spectra]

    names = [name for name, _ in spectra]
    selected = [names[0]]  # Start with first

    while len(selected) < k:
        # Find item that maximizes minimum distance to selected set
        best_name = None
        best_min_dist = -1.0

        for name in names:
            if name in selected:
                continue
            min_dist = min(matrix[name][s] for s in selected)
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_name = name

        if best_name:
            selected.append(best_name)
        else:
            break

    return selected


def compute_diversity_stats(matrix: dict[str, dict[str, float]]) -> dict[str, float]:
    """Compute diversity statistics from distance matrix."""
    distances = []
    names = list(matrix.keys())
    for i, name_i in enumerate(names):
        for j in range(i + 1, len(names)):
            name_j = names[j]
            distances.append(matrix[name_i][name_j])

    if not distances:
        return {
            "mean_distance": 0.0,
            "min_distance": 0.0,
            "max_distance": 0.0,
            "std_distance": 0.0,
        }

    mean_d = sum(distances) / len(distances)
    variance = sum((d - mean_d) ** 2 for d in distances) / len(distances)

    return {
        "mean_distance": round(mean_d, 6),
        "min_distance": round(min(distances), 6),
        "max_distance": round(max(distances), 6),
        "std_distance": round(math.sqrt(variance), 6),
    }


def generate_demo_graphs() -> list[tuple[str, "nx.Graph"]]:
    """Generate diverse graph types for demo."""
    return [
        ("path_20", nx.path_graph(20)),
        ("path_50", nx.path_graph(50)),
        ("cycle_20", nx.cycle_graph(20)),
        ("cycle_50", nx.cycle_graph(50)),
        ("complete_8", nx.complete_graph(8)),
        ("complete_12", nx.complete_graph(12)),
        ("star_15", nx.star_graph(15)),
        ("star_30", nx.star_graph(30)),
        ("grid_5x5", nx.grid_2d_graph(5, 5)),
        ("grid_7x7", nx.grid_2d_graph(7, 7)),
        ("petersen", nx.petersen_graph()),
        ("karate", nx.karate_club_graph()),
        ("erdos_renyi_40_01", nx.erdos_renyi_graph(40, 0.1, seed=42)),
        ("erdos_renyi_40_02", nx.erdos_renyi_graph(40, 0.2, seed=42)),
        ("erdos_renyi_40_03", nx.erdos_renyi_graph(40, 0.3, seed=42)),
        ("barabasi_albert_40_2", nx.barabasi_albert_graph(40, 2, seed=42)),
        ("barabasi_albert_40_3", nx.barabasi_albert_graph(40, 3, seed=42)),
        ("watts_strogatz_40_01", nx.watts_strogatz_graph(40, 4, 0.1, seed=42)),
        ("watts_strogatz_40_03", nx.watts_strogatz_graph(40, 4, 0.3, seed=42)),
        ("ladder_10", nx.ladder_graph(10)),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fingerprints",
        default="artifacts/conformance/graph_fingerprints_v1.json",
        help="Input fingerprints file (from compute_graph_fingerprints.py)",
    )
    parser.add_argument(
        "--output",
        default="artifacts/conformance/fixture_diversity_v1.json",
        help="Output diversity report",
    )
    parser.add_argument(
        "--select-k",
        type=int,
        default=10,
        help="Number of diverse fixtures to select",
    )
    parser.add_argument(
        "--spectrum-k",
        type=int,
        default=15,
        help="Number of Laplacian eigenvalues to use",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate demo diversity report",
    )
    args = parser.parse_args()

    if not HAS_DEPS:
        raise SystemExit("numpy and networkx are required: pip install numpy networkx")

    spectra: list[tuple[str, list[float]]] = []

    if args.demo:
        print("Generating demo diversity report...")
        graphs = generate_demo_graphs()
        for name, g in graphs:
            spec = laplacian_spectrum(g, k=args.spectrum_k)
            spectra.append((name, spec))
            print(f"  {name}: {len(spec)} eigenvalues")
    else:
        fingerprints_path = Path(args.fingerprints)
        if not fingerprints_path.exists():
            raise SystemExit(f"missing fingerprints file: {fingerprints_path}")

        data = safe_json_loads(fingerprints_path.read_text(encoding="utf-8"))
        if data is None or not isinstance(data, dict):
            raise SystemExit(f"invalid fingerprints file: {fingerprints_path}")
        for fp in data.get("fingerprints", []):
            name = fp.get("fixture_path", "unknown")
            eigenvalues = fp.get("spectral", {}).get("eigenvalues", [])
            if eigenvalues:
                spectra.append((name, eigenvalues))

        print(f"Loaded {len(spectra)} spectra from fingerprints")

    if not spectra:
        raise SystemExit("no spectra found")

    print(f"Computing {len(spectra)}x{len(spectra)} distance matrix...")
    matrix = spectral_diversity_matrix(spectra)

    print(f"Selecting {args.select_k} diverse fixtures...")
    selected = greedy_diverse_selection(spectra, args.select_k, matrix)

    stats = compute_diversity_stats(matrix)
    print(f"Diversity stats: mean={stats['mean_distance']:.4f}, "
          f"min={stats['min_distance']:.4f}, max={stats['max_distance']:.4f}")

    # Compute diversity stats for selected subset
    selected_matrix = {
        name: {k: v for k, v in row.items() if k in selected}
        for name, row in matrix.items()
        if name in selected
    }
    selected_stats = compute_diversity_stats(selected_matrix)

    payload = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "demo" if args.demo else str(args.fingerprints),
        "spectrum_k": args.spectrum_k,
        "fixture_count": len(spectra),
        "diversity_stats": stats,
        "selected_count": len(selected),
        "selected_diversity_stats": selected_stats,
        "selected_fixtures": selected,
        "distance_matrix_sample": {
            name: {
                k: v
                for k, v in list(row.items())[:5]  # Sample first 5 columns
            }
            for name, row in list(matrix.items())[:5]  # Sample first 5 rows
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"fixture_diversity:{output_path}")
    print(f"Selected {len(selected)} diverse fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
