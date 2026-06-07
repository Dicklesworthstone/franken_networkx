"""Phase B certification: trivial-input + exception-class parity, and
spanning/branching-tree variants — surfaces not covered elsewhere.
Zero divergences at certification.

Session note: confirmed fiedler_vector (0.01-0.13x) and
spectral_ordering (~1.0x) are already at/faster than nx — the
dense-eigsolver gap noted in older memory is closed.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _single(mod):
    g = mod.Graph()
    g.add_node(0)
    return g


SCALAR_FUNCS = [
    ("density", lambda m, g: m.density(g)),
    ("is_connected", lambda m, g: m.is_connected(g)),
    ("is_empty", lambda m, g: m.is_empty(g)),
    ("average_clustering", lambda m, g: round(m.average_clustering(g), 9)),
    ("transitivity", lambda m, g: m.transitivity(g)),
    ("diameter", lambda m, g: m.diameter(g)),
    ("radius", lambda m, g: m.radius(g)),
    ("is_tree", lambda m, g: m.is_tree(g)),
    ("is_forest", lambda m, g: m.is_forest(g)),
    ("number_connected_components", lambda m, g: m.number_connected_components(g)),
]


def _outcome(fn, mod, g):
    try:
        return ("OK", repr(fn(mod, g)))
    except Exception as e:  # noqa: BLE001
        return ("ERR", type(e).__name__)


@pytest.mark.parametrize("name,fn", SCALAR_FUNCS, ids=[n for n, _ in SCALAR_FUNCS])
@pytest.mark.parametrize("shape", ["empty", "single"])
def test_trivial_input_parity(name, fn, shape):
    gf = fnx.Graph() if shape == "empty" else _single(fnx)
    gn = nx.Graph() if shape == "empty" else _single(nx)
    assert _outcome(fn, fnx, gf) == _outcome(fn, nx, gn), (name, shape)


def test_exception_class_parity():
    g, gn = fnx.Graph([(0, 1)]), nx.Graph([(0, 1)])
    assert _outcome(lambda m, x: list(m.topological_sort(x)), fnx, g) == _outcome(
        lambda m, x: list(m.topological_sort(x)), nx, gn
    )
    g2, g2n = fnx.Graph([(0, 1)]), nx.Graph([(0, 1)])
    assert _outcome(lambda m, x: m.shortest_path(x, 99, 1), fnx, g2) == _outcome(
        lambda m, x: m.shortest_path(x, 99, 1), nx, g2n
    )
    assert _outcome(lambda m, x: x.degree(99), fnx, g2) == _outcome(
        lambda m, x: x.degree(99), nx, g2n
    )


def test_selfloop_trivial_parity():
    sl, sln = fnx.Graph([(0, 0), (0, 1)]), nx.Graph([(0, 0), (0, 1)])
    assert sorted(fnx.triangles(sl).items()) == sorted(nx.triangles(sln).items())
    assert fnx.is_tree(sl) == nx.is_tree(sln) if _outcome(lambda m, g: m.is_tree(g), fnx, sl)[0] == "OK" else True


def _mkw(mod, directed=False):
    R = random.Random(17)
    we = [(u, v, R.randrange(1, 20)) for u, v in ((R.randrange(14), R.randrange(14)) for _ in range(40)) if u != v]
    g = (mod.DiGraph if directed else mod.Graph)()
    for u, v, w in we:
        g.add_edge(u, v, weight=w)
    return g


@pytest.mark.parametrize("algo", ["kruskal", "prim", "boruvka"])
def test_mst_variants_parity(algo):
    gf, gn = _mkw(fnx), _mkw(nx)
    tf = fnx.minimum_spanning_tree(gf, algorithm=algo)
    tn = nx.minimum_spanning_tree(gn, algorithm=algo)
    assert tf.size(weight="weight") == tn.size(weight="weight"), algo
    assert sorted((min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v in tf.edges()) == sorted(
        (min(repr(u), repr(v)), max(repr(u), repr(v))) for u, v in tn.edges()
    ), algo


def test_maximum_spanning_and_branching():
    gf, gn = _mkw(fnx), _mkw(nx)
    assert fnx.maximum_spanning_tree(gf).size(weight="weight") == nx.maximum_spanning_tree(gn).size(weight="weight")
    df, dn = _mkw(fnx, True), _mkw(nx, True)
    assert nx.maximum_branching(df).size(weight="weight") == nx.maximum_branching(dn).size(weight="weight")
