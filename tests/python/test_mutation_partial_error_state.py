"""Mutation-state batch 2 (sibling of br-r37-c1-baqyi): nx mutates
INLINE — a malformed element mid-bunch raises nx's exact error AFTER
the valid prefix took effect, and add_edge creates u BEFORE examining
v. Matrix: malformed cases x 4 classes x (error, node set+attrs, edge
set with data/keys).
"""

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _base(mod, cls):
    g = getattr(mod, cls)()
    g.add_edge(0, 1, w=1)
    g.add_edge(1, 2, w=2)
    g.add_node("iso")
    return g


def _state(g, err):
    if g.is_multigraph():
        edges = sorted(repr(e) for e in g.edges(keys=True, data=True))
    else:
        edges = sorted(repr(e) for e in g.edges(data=True))
    return (err, sorted(map(repr, g)), edges)


MUTS = [
    ("ren none mid", lambda g: g.remove_edges_from([(0, 1), None, (1, 2)])),
    ("ren 1-tuple mid", lambda g: g.remove_edges_from([(0, 1), (2,), (1, 2)])),
    ("ren unhash mid", lambda g: g.remove_edges_from([(0, 1), ([1], 2), (1, 2)])),
    ("rnf unhash mid", lambda g: g.remove_nodes_from([0, [1], 2])),
    ("rnf missing mid", lambda g: g.remove_nodes_from([0, 99, 2])),
    ("anf unhash mid", lambda g: g.add_nodes_from([5, [6], 7])),
    ("upd edges bad mid", lambda g: g.update(edges=[(5, 6), (7, None)])),
    ("awef unhash mid", lambda g: g.add_weighted_edges_from([(5, 6, 1.0), ([7], 8, 2.0)])),
]


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("label,fn", MUTS)
def test_mutation_partial_state(cls, label, fn):
    gn, gf = _base(nx, cls), _base(fnx, cls)
    try:
        fn(gn)
        en = None
    except Exception as e:
        en = (type(e).__name__, str(e)[:50])
    try:
        fn(gf)
        ef = None
    except Exception as e:
        ef = (type(e).__name__, str(e)[:50])
    assert _state(gn, en) == _state(gf, ef)


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize(
    "args", [(5, None), (5, [6]), (None, 6), ([5], 6)], ids=["vN", "vU", "uN", "uU"]
)
def test_add_edge_creates_u_before_v_error(cls, args):
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    try:
        gn.add_edge(*args)
        en = None
    except Exception as e:
        en = type(e).__name__
    try:
        gf.add_edge(*args)
        ef = None
    except Exception as e:
        ef = type(e).__name__
    assert (en, sorted(map(repr, gn))) == (ef, sorted(map(repr, gf)))


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_remove_edge_missing_pair_message_omits_key(cls):
    """Mutation matrix r3: nx's `self._adj[u][v]` KeyError fires BEFORE
    key handling — a missing PAIR reports without the key; only a
    present pair with a missing KEY mentions it."""
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    for g in (gn, gf):
        g.add_edge(0, 1, key="k")
    # missing pair WITH explicit key: no key in message
    try:
        gn.remove_edge(5, 6, key=0)
    except Exception as e:
        en = (type(e).__name__, str(e))
    try:
        gf.remove_edge(5, 6, key=0)
    except Exception as e:
        ef = (type(e).__name__, str(e))
    assert en == ef
    assert "with key" not in en[1]
    # present pair, missing key: key in message
    try:
        gn.remove_edge(0, 1, key="zz")
    except Exception as e:
        en = (type(e).__name__, str(e))
    try:
        gf.remove_edge(0, 1, key="zz")
    except Exception as e:
        ef = (type(e).__name__, str(e))
    assert en == ef
    assert "with key zz" in en[1]
