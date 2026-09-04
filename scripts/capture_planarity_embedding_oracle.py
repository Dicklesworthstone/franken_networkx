#!/usr/bin/env python3
"""Capture NetworkX check_planarity embedding fixtures for the native
PlanarEmbedding port (reality-check bead rc-planar-embedding-kernel-07rh8,
milestone 1).

Every corpus entry records the EXACT node/edge insertion order used to build
the nx graph (embedding output depends on insertion order via the
copy()-adjacency walk), runs nx.check_planarity, and records the is-planar
verdict plus the embedding data (PlanarEmbedding.get_data() — per-node
clockwise neighbor orders) as the byte-parity oracle the Rust port must
reproduce exactly.

Output: tests/fixtures/planarity_embedding_oracle.json
Deterministic: fixed seeds, no clock, no hash-order dependence.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "tests" / "fixtures" / "planarity_embedding_oracle.json"


def k4() -> list[list[str]]:
    return [["0", "1"], ["0", "2"], ["1", "2"], ["0", "3"], ["1", "3"], ["2", "3"]]


def k5() -> list[list[str]]:
    return [[f"n{i}", f"n{j}"] for i in range(5) for j in range(i + 1, 5)]


def k33() -> list[list[str]]:
    return [[f"u{i}", f"v{j}"] for i in range(3) for j in range(3)]


def k26() -> list[list[str]]:
    return [[f"u{i}", f"v{j}"] for i in range(2) for j in range(6)]


def petersen() -> list[list[str]]:
    outer = [[str(i), str((i + 1) % 5)] for i in range(5)]
    spokes = [[str(i), str(i + 5)] for i in range(5)]
    inner = [[str(5 + i), str(5 + (i + 2) % 5)] for i in range(5)]
    return [*outer, *spokes, *inner]


def cube3() -> list[list[str]]:
    nodes = [f"{i:03b}" for i in range(8)]
    out = []
    for i, a in enumerate(nodes):
        for b in bit_flip_successors(a, i):
            out.append([a, b])
    return out


def bit_flip_successors(bits: str, index: int) -> list[str]:
    # successors of `bits` among nodes that come later in the enumeration
    out = []
    for j in range(index + 1, 8):
        other = f"{j:03b}"
        if sum(a != b for a, b in zip(bits, other)) == 1:
            out.append(other)
    return out


def octahedron() -> list[list[str]]:
    # K6 minus the perfect matching (0,3), (1,4), (2,5)
    return [
        [f"n{i}", f"n{j}"]
        for i in range(6)
        for j in range(i + 1, 6)
        if j - i != 3
    ]


def cycle(n: int, labels: list[str] | None = None) -> list[list[str]]:
    names = labels or [str(i) for i in range(n)]
    return [[names[i], names[(i + 1) % n]] for i in range(n)]


def star(n: int) -> list[list[str]]:
    return [[str(n), str(i)] for i in range(n)]


def corpus() -> dict[str, tuple[list[str], list[list[str]]]]:
    out: dict[str, tuple[list[str], list[list[str]]]] = {}
    out["K4"] = (["0", "1", "2", "3"], k4())
    out["K5_nonplanar"] = ([f"n{i}" for i in range(5)], k5())
    out["K33_nonplanar"] = ([f"u{i}" for i in range(3)] + [f"v{j}" for j in range(3)], k33())
    out["K26_nonplanar"] = (["u0", "u1"] + [f"v{j}" for j in range(6)], k26())
    out["petersen_nonplanar"] = ([str(i) for i in range(10)], petersen())
    out["cube3"] = [f"{i:03b}" for i in range(8)], cube3()
    out["octahedron"] = ([f"n{i}" for i in range(6)], octahedron())
    out["cycle_12"] = ([str(i) for i in range(12)], cycle(12))
    out["nonlex_cycle_6"] = (
        ["zz", "mm", "bb", "qq", "tt", "yy"],
        cycle(6, ["zz", "mm", "bb", "qq", "tt", "yy"]),
    )
    out["star_9"] = ([str(i) for i in range(10)], star(9))
    out["K4_with_chords_extra"] = (
        ["a", "b", "c", "d", "e"],
        [["a", "b"], ["b", "c"], ["c", "d"], ["d", "e"], ["e", "a"], ["a", "c"], ["b", "d"]],
    )
    return out


def seeded_randoms() -> dict[str, tuple[list[str], list[list[str]]]]:
    import random

    specs = {
        "er_planar_sparse_30": (30, 0.08),
        "er_planar_sparse_60": (60, 0.04),
        "er_dense_30_nonplanar": (30, 0.5),
        "er_mixed_80": (80, 0.05),
        "er_mixed_120": (120, 0.03),
    }
    out: dict[str, tuple[list[str], list[list[str]]]] = {}
    for idx, (name, (n, p)) in enumerate(specs.items()):
        rng = random.Random(1000 + idx)
        nodes = [f"n{i}" for i in range(n)]
        edges: list[list[str]] = []
        for i in range(n):
            for j in range(i + 1, n):
                if rng.random() < p:
                    edges.append([nodes[i], nodes[j]])
        out[name] = (nodes, edges)
    return out


def main() -> int:
    corpus_all = {**corpus(), **seeded_randoms()}
    fixtures = {"schema_version": 1, "graphs": {}}
    planar_count = 0
    for name in sorted(corpus_all):
        nodes, edges = corpus_all[name]
        g = nx.Graph()
        g.add_nodes_from(nodes)
        g.add_edges_from((u, v) for u, v in edges)
        is_planar, embedding = nx.check_planarity(g)
        entry: dict = {
            "nodes": list(g.nodes()),
            "edges": [list(e) for e in g.edges()],
            "build_edge_order": edges,
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
