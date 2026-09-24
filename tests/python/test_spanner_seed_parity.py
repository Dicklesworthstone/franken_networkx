"""spanner returns networkx's spanner for the same seed (nro4w.7).

The native kernel (br-r37-c1-va1lb) built a valid spanner with different
random draws and tie-breaks, so the same seed gave different edges; under
the fnx test backend networkx's five test_sparsifiers spanner tests failed
their exact-result comparison. fnx now runs networkx's Baswana-Sen step for
step. Its tie-breakers are id(u), id(v), so exact equality is defined when
both libraries hold the same node objects: small ints, strings. That is
networkx's own reproducibility boundary; for other nodes the result is a
valid spanner and deterministic.
"""

from __future__ import annotations

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _shape(H):
    return list(H.nodes), list(H.edges(data=True))


def _random_case(rng, labels):
    n = len(labels)
    edges = [
        (labels[rng.randrange(n)], labels[rng.randrange(n)], {"w": rng.choice([1, 2, 0.5, 3])})
        for _ in range(rng.randint(0, 60))
    ]
    return edges, rng.choice([1, 2, 3, 4, 5, 7]), rng.choice([None, "w"]), rng.randint(0, 99)


@pytest.mark.parametrize("labels_kind", ["small_ints", "strings"])
@pytest.mark.parametrize("seed_kind", ["int", "random.Random"])
def test_same_seed_gives_networkx_spanner(labels_kind, seed_kind):
    rng = random.Random(f"{labels_kind}-{seed_kind}")
    for _ in range(60):
        n = rng.randint(1, 25)
        labels = list(range(n)) if labels_kind == "small_ints" else [f"n{i}" for i in range(n)]
        edges, stretch, weight, s = _random_case(rng, labels)
        results = []
        for module in (nx, fnx):
            G = module.Graph()
            G.add_nodes_from(labels)
            G.add_edges_from(edges)
            seed = s if seed_kind == "int" else random.Random(s)
            results.append(_shape(module.spanner(G, stretch, weight=weight, seed=seed)))
        assert results[1] == results[0], (labels, edges, stretch, weight, s)


@pytest.mark.parametrize("weighted", [False, True])
def test_networkx_sparsifier_fixtures(weighted):
    # networkx's test_spanner_{un,}weighted_complete_graph / _gnp_graph inputs.
    for build in (lambda m: m.complete_graph(20), lambda m: m.gnp_random_graph(20, 0.4, seed=10)):
        results = []
        for module in (nx, fnx):
            G = build(module)
            if weighted:
                wrng = random.Random(10)
                for u, v in G.edges():
                    G[u][v]["weight"] = wrng.random()
            results.append(
                [_shape(module.spanner(G, s, weight="weight" if weighted else None, seed=10)) for s in (4, 10)]
            )
        assert results[1] == results[0]


def _is_valid_spanner(G, H, stretch, weight):
    if set(G) != set(H) or any(not G.has_edge(u, v) for u, v in H.edges()):
        return False
    original = dict(nx.shortest_path_length(G, weight=weight))
    spanned = dict(nx.shortest_path_length(H, weight=weight))
    return all(spanned[u][v] <= stretch * original[u][v] + 1e-9 for u in original for v in original[u])


def test_other_nodes_get_a_valid_deterministic_spanner():
    rng = random.Random(3)
    for _ in range(40):
        labels = [10**6 + i for i in range(rng.randint(1, 20))]
        edges, stretch, weight, s = _random_case(rng, labels)
        G = fnx.Graph()
        G.add_nodes_from(labels)
        G.add_edges_from(edges)
        H1 = fnx.spanner(G, stretch, weight=weight, seed=s)
        assert _shape(fnx.spanner(G, stretch, weight=weight, seed=s)) == _shape(H1)
        NG = nx.Graph()
        NG.add_nodes_from(labels)
        NG.add_edges_from(edges)
        NH = nx.Graph()
        NH.add_nodes_from(H1.nodes)
        NH.add_edges_from(H1.edges(data=True))
        assert _is_valid_spanner(NG, NH, stretch, weight)
