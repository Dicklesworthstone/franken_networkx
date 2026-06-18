"""Graph binary/unary operators: differential parity + set-algebra laws.

Operators that build a new graph from one or two inputs obey set-algebra
identities on their edge sets — complement is the set complement within K_n,
compose is union, intersection is set intersection, and complement is an
involution. Checking the laws alongside nx parity catches structural and
off-by-one bugs.

No mocks: real fnx and real networkx on identically-built random graphs.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx


def _edge_set(g):
    return {tuple(sorted((u, v))) for u, v in g.edges()}


def _pair(seed):
    """Two graphs on the same node set, built identically in fnx and nx."""
    r = random.Random(seed)
    n = r.randint(4, 7)

    def build(lib, rng):
        g = lib.Graph()
        g.add_nodes_from(range(n))
        for u in range(n):
            for v in range(u + 1, n):
                if rng.random() < 0.45:
                    g.add_edge(u, v)
        return g

    st = r.getstate(); fg = build(fnx, r)
    r.setstate(st); ng = build(nx, r)
    st2 = r.getstate(); fh = build(fnx, r)
    r.setstate(st2); nh = build(nx, r)
    return fg, ng, fh, nh, n


@pytest.mark.parametrize("seed", range(50))
def test_complement_parity_and_involution(seed):
    fg, ng, _, _, n = _pair(seed)
    assert _edge_set(fnx.complement(fg)) == _edge_set(nx.complement(ng))
    # G and complement partition the complete graph's edges.
    comp = _edge_set(fnx.complement(fg))
    orig = _edge_set(fg)
    all_pairs = {(u, v) for u in range(n) for v in range(u + 1, n)}
    assert comp | orig == all_pairs
    assert not (comp & orig)


@pytest.mark.parametrize("seed", range(50))
def test_binary_operators_parity_and_laws(seed):
    fg, ng, fh, nh, n = _pair(seed)
    ef, eh = _edge_set(fg), _edge_set(fh)

    assert _edge_set(fnx.compose(fg, fh)) == _edge_set(nx.compose(ng, nh))
    assert _edge_set(fnx.compose(fg, fh)) == ef | eh

    assert _edge_set(fnx.intersection(fg, fh)) == _edge_set(nx.intersection(ng, nh))
    assert _edge_set(fnx.intersection(fg, fh)) == ef & eh

    assert _edge_set(fnx.difference(fg, fh)) == _edge_set(nx.difference(ng, nh))
    assert _edge_set(fnx.difference(fg, fh)) == ef - eh

    assert _edge_set(fnx.symmetric_difference(fg, fh)) == _edge_set(
        nx.symmetric_difference(ng, nh)
    )
    assert _edge_set(fnx.symmetric_difference(fg, fh)) == ef ^ eh


@pytest.mark.parametrize("seed", range(40))
def test_products_size_parity(seed):
    fg, ng, fh, nh, n = _pair(seed)
    for fprod, nprod in [
        (fnx.cartesian_product, nx.cartesian_product),
        (fnx.tensor_product, nx.tensor_product),
        (fnx.strong_product, nx.strong_product),
    ]:
        fp = fprod(fg, fh)
        np_ = nprod(ng, nh)
        assert fp.number_of_nodes() == np_.number_of_nodes()
        assert fp.number_of_edges() == np_.number_of_edges()
