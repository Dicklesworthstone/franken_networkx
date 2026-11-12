"""Differential + metamorphic parity for the isomorphism-check family.

Covers the necessary-condition predicates ``faster_could_be_isomorphic``
(degree sequence), ``fast_could_be_isomorphic`` (degree + triangle
sequence) and ``could_be_isomorphic`` (degree + triangle + clique
sequence), plus the exact deciders ``is_isomorphic`` and
``vf2pp_is_isomorphic``. None had a dedicated test file.

This locks fnx against the real upstream networkx with:

* differential parity across random graph pairs (undirected and
  directed) and under categorical node/edge attribute matching,
* metamorphic invariants independent of the reference — a relabeled
  graph is isomorphic to itself, and ``is_isomorphic`` implies each
  necessary-condition predicate, and
* structural-negative goldens (different degree sequences cannot be
  isomorphic).

br-r37-c1-j8yqy
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx
from networkx.algorithms.isomorphism import categorical_node_match

_NECESSARY = [
    "could_be_isomorphic",
    "fast_could_be_isomorphic",
    "faster_could_be_isomorphic",
]
_DECIDERS = ["is_isomorphic", "vf2pp_is_isomorphic"]
_ALL_PREDICATES = _NECESSARY + _DECIDERS


def _build(seed, lib, n=None, p=0.4):
    rng = random.Random(seed)
    if n is None:
        n = rng.randint(4, 9)
    g = lib.Graph()
    g.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                g.add_edge(u, v)
    return g


# ---------------------------------------------------------------------------
# Differential parity across random pairs.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", _ALL_PREDICATES)
@pytest.mark.parametrize("seed", range(40))
def test_isomorphism_predicate_matches_networkx(fn, seed):
    fa, fb = _build(seed, fnx), _build(seed + 1000, fnx)
    na, nb = _build(seed, nx), _build(seed + 1000, nx)
    assert getattr(fnx, fn)(fa, fb) == getattr(nx, fn)(na, nb), f"{fn} seed={seed}"


@pytest.mark.parametrize("seed", range(30))
def test_vf2pp_directed_matches_networkx(seed):
    def directed(lib, sd):
        rng = random.Random(sd)
        n = rng.randint(4, 7)
        g = lib.DiGraph()
        g.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u != v and rng.random() < 0.3:
                    g.add_edge(u, v)
        return g

    fa, fb = directed(fnx, seed), directed(fnx, seed + 7)
    na, nb = directed(nx, seed), directed(nx, seed + 7)
    assert fnx.vf2pp_is_isomorphic(fa, fb) == nx.vf2pp_is_isomorphic(na, nb)


# ---------------------------------------------------------------------------
# Attribute-aware matching parity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(30))
def test_is_isomorphic_with_node_attr_match_parity(seed):
    fa, na = _build(seed, fnx), _build(seed, nx)
    for node in fa.nodes():
        fa.nodes[node]["c"] = node % 2
    for node in na.nodes():
        na.nodes[node]["c"] = node % 2
    nm = categorical_node_match("c", None)
    assert fnx.is_isomorphic(fa, fa, node_match=nm) == nx.is_isomorphic(na, na, node_match=nm)


# ---------------------------------------------------------------------------
# Metamorphic invariants.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", _ALL_PREDICATES)
@pytest.mark.parametrize("seed", range(30))
def test_relabeled_graph_is_isomorphic_to_itself(fn, seed):
    g = _build(seed, fnx)
    n = g.number_of_nodes()
    perm = list(range(n))
    random.Random(seed * 3 + 1).shuffle(perm)
    relabeled = fnx.relabel_nodes(g, {i: perm[i] for i in range(n)})
    assert getattr(fnx, fn)(g, relabeled), f"{fn}: relabeled graph not isomorphic to itself"


@pytest.mark.parametrize("seed", range(40))
def test_is_isomorphic_implies_necessary_conditions(seed):
    fa, fb = _build(seed, fnx), _build(seed + 5, fnx)
    if fnx.is_isomorphic(fa, fb):
        for fn in _NECESSARY:
            assert getattr(fnx, fn)(fa, fb), (
                f"{fn} must hold whenever is_isomorphic is True (seed={seed})"
            )


# ---------------------------------------------------------------------------
# Structural-negative goldens.
# ---------------------------------------------------------------------------


def test_distinct_structures_are_not_isomorphic():
    # Path P4 and star S3 both have 4 nodes & 3 edges but different degree
    # sequences, so they are not isomorphic — and the cheap necessary-
    # condition predicates already rule it out.
    p4 = fnx.path_graph(4)
    s3 = fnx.star_graph(3)
    for fn in _ALL_PREDICATES:
        assert not getattr(fnx, fn)(p4, s3), f"{fn} wrongly accepted P4 vs S3"
    # Triangle vs P3: 3 nodes, but 3 vs 2 edges.
    assert not fnx.is_isomorphic(fnx.cycle_graph(3), fnx.path_graph(3))


def test_identical_graphs_are_isomorphic():
    for fn in _ALL_PREDICATES:
        assert getattr(fnx, fn)(fnx.complete_graph(5), fnx.complete_graph(5))
        assert getattr(fnx, fn)(fnx.cycle_graph(6), fnx.cycle_graph(6))
