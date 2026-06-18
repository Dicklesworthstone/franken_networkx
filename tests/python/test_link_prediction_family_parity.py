"""Differential + golden parity for the core link-prediction family.

``jaccard_coefficient``, ``adamic_adar_index``,
``resource_allocation_index`` and ``preferential_attachment`` each return
a lazy iterator of ``(u, v, score)`` triples — over a supplied ``ebunch``
of node pairs, or over all non-edges by default. None had a dedicated
test file.

This locks fnx against the real upstream networkx with:

* differential parity (including *exact* iteration order) for every
  function, over random graphs, with both the default ebunch and an
  explicit one,
* hand-computed score goldens on a small fixed graph,
* the lazy-iterator contract, and
* the directed / multigraph ``NetworkXNotImplemented`` contract.

br-r37-c1-swpt8
"""

from __future__ import annotations

import math
import random

import pytest
import networkx as nx

import franken_networkx as fnx


_FUNCS = [
    "jaccard_coefficient",
    "adamic_adar_index",
    "resource_allocation_index",
    "preferential_attachment",
]


def _pair(seed, p=0.35):
    rng = random.Random(seed)
    n = rng.randint(5, 11)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    edges = [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]
    fg.add_edges_from(edges)
    ng.add_edges_from(edges)
    return fg, ng, n


def _materialize(it):
    # Preserve order; round scores so float reps compare cleanly.
    return [(u, v, round(s, 9)) for u, v, s in it]


# ---------------------------------------------------------------------------
# Differential parity (exact iteration order).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize("seed", range(40))
def test_link_prediction_default_ebunch_matches_networkx(fn, seed):
    fg, ng, _ = _pair(seed)
    fr = _materialize(getattr(fnx, fn)(fg))
    nr = _materialize(getattr(nx, fn)(ng))
    assert fr == nr, f"{fn} seed={seed}: order/value mismatch"


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize("seed", range(40))
def test_link_prediction_explicit_ebunch_matches_networkx(fn, seed):
    fg, ng, n = _pair(seed)
    rng = random.Random(seed * 13 + 1)
    all_pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    rng.shuffle(all_pairs)
    ebunch = all_pairs[: min(6, len(all_pairs))]
    fr = _materialize(getattr(fnx, fn)(fg, ebunch))
    nr = _materialize(getattr(nx, fn)(ng, ebunch))
    assert fr == nr, f"{fn} seed={seed} ebunch={ebunch}: mismatch"


# ---------------------------------------------------------------------------
# Hand-computed goldens on a fixed graph: triangle 0-1-2 with tail 2-3.
# ---------------------------------------------------------------------------


def _golden_graph():
    return fnx.Graph([(0, 1), (1, 2), (2, 0), (2, 3)])


def test_jaccard_golden():
    # pair (0, 3): common neighbors = {2}; union of neighbors = {1, 2} → 1/2.
    [(u, v, score)] = list(fnx.jaccard_coefficient(_golden_graph(), [(0, 3)]))
    assert (u, v) == (0, 3)
    assert score == pytest.approx(0.5)


def test_resource_allocation_golden():
    # pair (0, 3): common neighbor 2 with degree 3 → 1/3.
    [(_, _, score)] = list(fnx.resource_allocation_index(_golden_graph(), [(0, 3)]))
    assert score == pytest.approx(1 / 3)


def test_adamic_adar_golden():
    # pair (0, 3): common neighbor 2 with degree 3 → 1/log(3).
    [(_, _, score)] = list(fnx.adamic_adar_index(_golden_graph(), [(0, 3)]))
    assert score == pytest.approx(1 / math.log(3))


def test_preferential_attachment_golden():
    # pair (0, 3): deg(0) = 2, deg(3) = 1 → 2.
    [(_, _, score)] = list(fnx.preferential_attachment(_golden_graph(), [(0, 3)]))
    assert score == 2


# ---------------------------------------------------------------------------
# Iterator contract and error contracts.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", _FUNCS)
def test_link_prediction_returns_lazy_iterator(fn):
    it = getattr(fnx, fn)(_golden_graph())
    assert iter(it) is iter(it)
    assert not isinstance(it, list)


@pytest.mark.parametrize("fn", _FUNCS)
@pytest.mark.parametrize(
    "fnx_cls,nx_cls",
    [(fnx.DiGraph, nx.DiGraph), (fnx.MultiGraph, nx.MultiGraph)],
)
def test_link_prediction_rejects_directed_and_multigraph(fn, fnx_cls, nx_cls):
    fg = fnx_cls([(0, 1), (1, 2)])
    ng = nx_cls([(0, 1), (1, 2)])
    with pytest.raises(nx.NetworkXNotImplemented):
        list(getattr(fnx, fn)(fg))
    with pytest.raises(nx.NetworkXNotImplemented):
        list(getattr(nx, fn)(ng))
