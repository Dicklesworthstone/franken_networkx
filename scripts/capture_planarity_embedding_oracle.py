#!/usr/bin/env python3
"""Capture NetworkX check_planarity embedding fixtures for the native
PlanarEmbedding port (reality-check bead rc-planar-embedding-kernel-07rh8,
milestone 1).

Generates a deterministic corpus (named classics + seeded random graphs),
runs nx.check_planarity on each, and records the is-planar verdict plus the
embedding data (`PlanarEmbedding.get_data()` — per-node clockwise neighbor
orders) as the byte-parity oracle the Rust port must reproduce exactly.

Output: tests/fixtures/planarity_embedding_oracle.json
Deterministic: fixed seeds, no clock, no hash-order dependence (dicts are
serialized with sort_keys=True).
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tests" / "fixtures" / "planarity_embedding_oracle.json"


def classics() -> dict[str, nx.Graph]:
    graphs: dict[str, nx.Graph] = {
        "K4": nx.complete_graph(4),
        "K5_nonplanar": nx.complete_graph(5),
        "K33_nonplanar": nx.complete_bipartite_graph(3, 3),
        "petersen_nonplanar": nx.petersen_graph(),
        "cube": nx.hypercube_graph(3),
        "octahedron": nx.octahedral_graph(),
        "cycle_12": nx.cycle_graph(12),
        "star_9": nx.star_graph(9),
        "K26_nonplanar": nx.complete_bipartite_graph(2, 6),
    }
    # normalize node labels to strings for stable JSON
    out = {}
    for name, g in graphs.items():
        h = nx.relabel_nodes(g, {n: str(n) for n in g})
        out[name] = h
    return out


def seeded_randoms() -> dict[str, nx.Graph]:
    import random

    out: dict[str, nx.Graph] = {}
    # Erdős–Rényi graphs: planar and non-planar instances.
    for idx, (name, (n, p)) in enumerate(
        {
            "er_planar_sparse_30": (30, 0.08),
            "er_planar_sparse_60": (60, 0.04),
            "er_dense_30_nonplanar": (30, 0.5),
            "er_mixed_80": (80, 0.05),
            "er_mixed_120": (120, 0.03),
        }.items()
    ):
        rng = random.Random(1000 + idx)
        g = nx.Graph()
        g.add_nodes_from((f"n{i}" for i in range(n)))
        for i in range(n):
            for j in range(i + 1, n):
                if rng.random() < p:
                    g.add_edge(f"n{i}", f"n{j}")
        out[name] = g
    # cycle so insertion order is deliberately not lexicographic.
    g = nx.Graph()
    labels = ["zz", "mm", "bb", "qq", "tt", "yy"]
    for i in range(len(labels)):
        g.add_edge(labels[i], labels[(i + 1) % len(labels)])
    out["nonlex_cycle_6"] = g
    return out


def main() -> int:
    corpus = {**classics(), **seeded_randoms()}
    fixtures = {"schema_version": 1, "graphs": {}}
    planar_count = 0
    for name in sorted(corpus):
        g = corpus[name]
        is_planar, embedding = nx.check_planarity(g)
        edges = [[u, v] for u, v in g.edges()]
        nodes = [str(n) for n in g.nodes()]
        entry: dict = {
            "nodes": nodes,
            "edges": edges,
            "is_planar": bool(is_planar),
        }
        if is_planar:
            data = embedding.get_data()
            entry["embedding_data"] = {
                str(k): [str(x) for x in v] for k, v in data.items()
            }
            planar_count += 1
        else:
            entry["embedding_data"] = None
        fixtures["graphs"][name] = entry

    fixtures["summary"] = {
        "networkx_version": nx.__version__,
        "graph_count": len(fixtures["graphs"]),
        "planar_count": planar_count,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fixtures, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT} ({len(fixtures['graphs'])} graphs, {planar_count} planar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
