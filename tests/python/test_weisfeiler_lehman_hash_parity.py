"""Differential + metamorphic parity for Weisfeiler-Lehman hashing.

``weisfeiler_lehman_graph_hash(G, ...)`` returns a deterministic md5
hex digest summarizing a graph up to the WL relabeling scheme, and
``weisfeiler_lehman_subgraph_hashes(G, ...)`` returns the per-node
hash histories. Neither had a dedicated test file.

This locks fnx against the real upstream networkx with:

* differential parity for the graph hash across graph classes,
  iteration counts, and ``node_attr`` / ``edge_attr`` colorings,
* differential parity for the per-node subgraph hashes,
* metamorphic invariants independent of the reference — the hash is
  isomorphism-invariant (relabeling nodes leaves it unchanged),
  deterministic, and a 32-char hex string, and
* sanity goldens — distinct small structures (C4 vs P4) hash
  differently, and the empty graph matches nx.

br-r37-c1-r3qxf
"""

from __future__ import annotations

import random

import pytest
import networkx as nx

import franken_networkx as fnx


def _pair(seed, fnx_cls, nx_cls, directed, p=0.35, node_attr=False, edge_attr=False):
    """Build the same random graph (with optional matched attrs) in both libs."""
    rng = random.Random(seed)
    n = rng.randint(4, 10)
    fg = fnx_cls()
    ng = nx_cls()
    for i in range(n):
        if node_attr:
            label = chr(65 + rng.randint(0, 2))
            fg.add_node(i, label=label)
            ng.add_node(i, label=label)
        else:
            fg.add_node(i)
            ng.add_node(i)
    for u in range(n):
        for v in range(n):
            if u == v:
                continue
            if (directed or u < v) and rng.random() < p:
                if edge_attr:
                    kind = rng.choice(["x", "y"])
                    fg.add_edge(u, v, kind=kind)
                    ng.add_edge(u, v, kind=kind)
                else:
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
    return fg, ng


_CLASSES = [
    (fnx.Graph, nx.Graph, False),
    (fnx.DiGraph, nx.DiGraph, True),
]


# ---------------------------------------------------------------------------
# Differential parity: graph hash.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fnx_cls,nx_cls,directed", _CLASSES,
                         ids=["Graph", "DiGraph"])
@pytest.mark.parametrize("iterations", [1, 2, 3, 5])
@pytest.mark.parametrize("seed", range(20))
def test_wl_graph_hash_matches_networkx(fnx_cls, nx_cls, directed, iterations, seed):
    fg, ng = _pair(seed, fnx_cls, nx_cls, directed)
    fr = fnx.weisfeiler_lehman_graph_hash(fg, iterations=iterations)
    nr = nx.weisfeiler_lehman_graph_hash(ng, iterations=iterations)
    assert fr == nr, f"seed={seed} it={iterations}: fnx={fr} nx={nr}"


@pytest.mark.parametrize("iterations", [1, 3, 5])
@pytest.mark.parametrize("seed", range(25))
def test_wl_graph_hash_with_attrs_matches_networkx(iterations, seed):
    fg, ng = _pair(seed, fnx.Graph, nx.Graph, False,
                   node_attr=True, edge_attr=True)
    fr = fnx.weisfeiler_lehman_graph_hash(
        fg, iterations=iterations, node_attr="label", edge_attr="kind"
    )
    nr = nx.weisfeiler_lehman_graph_hash(
        ng, iterations=iterations, node_attr="label", edge_attr="kind"
    )
    assert fr == nr, f"seed={seed} it={iterations}: fnx={fr} nx={nr}"


# ---------------------------------------------------------------------------
# Differential parity: per-node subgraph hashes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("iterations", [2, 3])
@pytest.mark.parametrize("seed", range(30))
def test_wl_subgraph_hashes_match_networkx(iterations, seed):
    fg, ng = _pair(seed, fnx.Graph, nx.Graph, False)
    fr = {str(k): v for k, v in
          fnx.weisfeiler_lehman_subgraph_hashes(fg, iterations=iterations).items()}
    nr = {str(k): v for k, v in
          nx.weisfeiler_lehman_subgraph_hashes(ng, iterations=iterations).items()}
    assert fr == nr, f"seed={seed} it={iterations}"


# ---------------------------------------------------------------------------
# Metamorphic invariants.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_wl_graph_hash_is_isomorphism_invariant(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg = fnx.Graph()
    fg.add_nodes_from(range(n))
    fg.add_edges_from(
        [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < 0.4]
    )
    perm = list(range(n))
    rng.shuffle(perm)
    relabeled = fnx.relabel_nodes(fg, {i: perm[i] for i in range(n)})
    assert (
        fnx.weisfeiler_lehman_graph_hash(fg)
        == fnx.weisfeiler_lehman_graph_hash(relabeled)
    ), f"seed={seed}: WL hash not isomorphism-invariant"


def test_wl_graph_hash_is_deterministic_and_hex():
    g = fnx.cycle_graph(6)
    h1 = fnx.weisfeiler_lehman_graph_hash(g)
    h2 = fnx.weisfeiler_lehman_graph_hash(g)
    assert h1 == h2
    assert len(h1) == 32
    assert all(c in "0123456789abcdef" for c in h1)


def test_wl_graph_hash_distinguishes_cycle_from_path():
    c4 = fnx.weisfeiler_lehman_graph_hash(fnx.cycle_graph(4))
    p4 = fnx.weisfeiler_lehman_graph_hash(fnx.path_graph(4))
    assert c4 != p4
    # ...and each still agrees with networkx.
    assert c4 == nx.weisfeiler_lehman_graph_hash(nx.cycle_graph(4))
    assert p4 == nx.weisfeiler_lehman_graph_hash(nx.path_graph(4))


def test_wl_graph_hash_empty_graph_matches_networkx():
    assert (
        fnx.weisfeiler_lehman_graph_hash(fnx.Graph())
        == nx.weisfeiler_lehman_graph_hash(nx.Graph())
    )
