"""Differential + metamorphic parity for the chordal-graph family.

Covers ``is_chordal``, ``chordal_graph_treewidth``,
``chordal_graph_cliques`` and ``complete_to_chordal_graph`` — all built
on maximum-cardinality-search elimination orderings, which are easy to
get subtly wrong. The family had only scattered coverage and no focused
test file.

This locks fnx against the real upstream networkx with:

* ``is_chordal`` differential parity on random graphs,
* ``chordal_graph_treewidth`` / ``chordal_graph_cliques`` parity on the
  chordal members of the random sample,
* ``complete_to_chordal_graph`` exact edge-set parity with nx, plus
  reference-independent metamorphic invariants — the completion is
  chordal and is an edge-superset of the input,
* hand-computed goldens, and
* the ``chordal_graph_treewidth`` non-chordal error contract.

br-r37-c1-srsis
"""

from __future__ import annotations

import importlib
import random

import pytest
import networkx as nx

import franken_networkx as fnx


def _pair(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(4, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng, n


def _edge_set(G):
    return {frozenset(e) for e in G.edges()}


def _expect(condition, message):
    if not condition:
        pytest.fail(message)


def test_chordal_module_public_surface_matches_networkx():
    module = importlib.import_module("franken_networkx.chordal")
    expected = importlib.import_module("networkx.algorithms.chordal")

    _expect(set(module.__all__) == set(expected.__all__), "chordal __all__ must match networkx")


def test_chordal_module_complete_to_chordal_graph_returns_fnx_graph(monkeypatch):
    module = importlib.import_module("franken_networkx.chordal")
    expected = importlib.import_module("networkx.algorithms.chordal")
    fg = fnx.cycle_graph(5)
    ng = nx.cycle_graph(5)

    fh, f_alpha = module.complete_to_chordal_graph(fg)
    nh, n_alpha = expected.complete_to_chordal_graph(ng)

    _expect(isinstance(fh, fnx.Graph), "complete_to_chordal_graph must return an fnx Graph")
    _expect(_edge_set(fh) == _edge_set(nh), "chordal completion edges must match networkx")
    _expect(f_alpha == n_alpha, "chordal alpha map must match networkx")

    sentinel = object()

    def fake_complete_to_chordal_graph(graph, *, backend=None, **kwargs):
        _expect(graph is fg, "complete_to_chordal_graph must forward the original graph")
        _expect(backend == "sentinel", "complete_to_chordal_graph must forward backend")
        _expect(kwargs == {"strict": True}, "complete_to_chordal_graph must forward backend kwargs")
        return sentinel

    monkeypatch.setattr(fnx, "complete_to_chordal_graph", fake_complete_to_chordal_graph)
    _expect(
        module.complete_to_chordal_graph(fg, backend="sentinel", strict=True) is sentinel,
        "chordal.complete_to_chordal_graph must route through fnx",
    )


# ---------------------------------------------------------------------------
# is_chordal.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_is_chordal_matches_networkx(seed):
    fg, ng, _ = _pair(seed)
    assert fnx.is_chordal(fg) == nx.is_chordal(ng), f"seed={seed}"


# ---------------------------------------------------------------------------
# treewidth + cliques on the chordal members of the sample.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(60))
def test_chordal_treewidth_and_cliques_match_networkx(seed):
    fg, ng, _ = _pair(seed)
    if not nx.is_chordal(ng):
        pytest.skip("treewidth/cliques require a chordal graph")
    assert fnx.chordal_graph_treewidth(fg) == nx.chordal_graph_treewidth(ng)
    fr = {frozenset(c) for c in fnx.chordal_graph_cliques(fg)}
    nr = {frozenset(c) for c in nx.chordal_graph_cliques(ng)}
    assert fr == nr, f"seed={seed}: clique sets differ"


# ---------------------------------------------------------------------------
# complete_to_chordal_graph: differential + metamorphic.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(50))
def test_complete_to_chordal_graph_matches_networkx(seed):
    fg, ng, _ = _pair(seed, p=0.3)
    fh, _ = fnx.complete_to_chordal_graph(fg)
    nh, _ = nx.complete_to_chordal_graph(ng)
    assert _edge_set(fh) == _edge_set(nh), f"seed={seed}: completion edges differ"


@pytest.mark.parametrize("seed", range(50))
def test_complete_to_chordal_graph_is_a_chordal_superset(seed):
    fg, _, _ = _pair(seed, p=0.3)
    fh, _ = fnx.complete_to_chordal_graph(fg)
    assert _edge_set(fg).issubset(_edge_set(fh)), "completion dropped edges"
    assert fnx.is_chordal(fh), "completion is not chordal"


# ---------------------------------------------------------------------------
# Hand-computed goldens.
# ---------------------------------------------------------------------------


def test_is_chordal_goldens():
    assert not fnx.is_chordal(fnx.cycle_graph(4))
    assert not fnx.is_chordal(fnx.cycle_graph(5))
    assert fnx.is_chordal(fnx.cycle_graph(3))
    # C4 plus a chord is chordal.
    assert fnx.is_chordal(fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]))
    # complete graphs and trees are chordal.
    assert fnx.is_chordal(fnx.complete_graph(5))
    assert fnx.is_chordal(fnx.path_graph(6))
    # is_chordal returns an actual bool, like networkx.
    assert isinstance(fnx.is_chordal(fnx.cycle_graph(4)), bool)


def test_chordal_treewidth_goldens():
    assert fnx.chordal_graph_treewidth(fnx.complete_graph(5)) == 4
    assert fnx.chordal_graph_treewidth(fnx.path_graph(6)) == 1


# ---------------------------------------------------------------------------
# Error contract.
# ---------------------------------------------------------------------------


def test_chordal_treewidth_rejects_non_chordal_like_networkx():
    with pytest.raises(nx.NetworkXError):
        fnx.chordal_graph_treewidth(fnx.cycle_graph(5))
    with pytest.raises(nx.NetworkXError):
        nx.chordal_graph_treewidth(nx.cycle_graph(5))
