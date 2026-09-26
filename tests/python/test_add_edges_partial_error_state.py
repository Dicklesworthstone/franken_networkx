"""br-r37-c1-baqyi: nx's add_edges_from / add_edge leave specific
PARTIAL state when an edge errors mid-call — fnx must match exactly:
- non-dict 3rd (simple graphs): BOTH endpoint nodes exist before
  dict.update raises;
- Multi 3-tuple: nx tries ddd.update(dd) FIRST — dict-able iterables of
  pairs are DATA, only TypeError/ValueError makes it the key;
- Multi unhashable key: nodes exist before the TypeError;
- Multi non-dict 4th: ddd.update raises BEFORE add_edge (nothing
  created);
- ctor wraps failures in NetworkXError('Input is not a valid edge
  list').
"""

import networkx as nx
import pytest

import franken_networkx as fnx

CASES = [
    ("float third", [(1, 2, 1.5)]),
    ("str third", [(1, 2, "ab")]),
    ("list-of-scalars third", [(1, 2, [3])]),
    ("kv-iterable third is data", [(1, 2, [("a", 3)])]),
    ("valid prefix + bad", [(0, 9), (1, 2, 1.5)]),
    ("4-tuple non-dict", [(1, 2, 3, 4)]),
    ("4-tuple kv-iter", [(1, 2, "k", [("a", 3)])]),
    ("bad after multi prefix", [(0, 9), (9, 8), (1, 2, "ab")]),
    ("parallel keys mixed", [(1, 2), (1, 2, "k1"), (1, 2), (1, 2, {"w": 5}), (1, 2, "k1", {"w": 9})]),
]


def _state(g, err):
    if g.is_multigraph():
        edges = sorted(repr(e) for e in g.edges(keys=True, data=True))
    else:
        edges = sorted(repr(e) for e in g.edges(data=True))
    return (err, sorted(map(repr, g)), edges)


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("label,ebunch", CASES)
def test_add_edges_from_partial_state(cls, label, ebunch):
    if label == "parallel keys mixed" and not cls.startswith("Multi"):
        pytest.skip("multi-only shape")
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    try:
        gn.add_edges_from(ebunch)
        en = None
    except Exception as e:
        en = (type(e).__name__, str(e)[:40])
    try:
        gf.add_edges_from(ebunch)
        ef = None
    except Exception as e:
        ef = (type(e).__name__, str(e)[:40])
    assert _state(gn, en) == _state(gf, ef)


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_unhashable_key_creates_nodes_first(cls):
    gn, gf = getattr(nx, cls)(), getattr(fnx, cls)()
    with pytest.raises(TypeError):
        gn.add_edge(1, 2, key=[3])
    with pytest.raises(TypeError):
        gf.add_edge(1, 2, key=[3])
    assert sorted(map(repr, gf)) == sorted(map(repr, gn)) == ["1", "2"]
    assert list(gf.edges()) == []


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_ctor_wraps_unhashable_in_edge_list_error(cls):
    try:
        getattr(nx, cls)([(1, 2, [3])])
        expected = None
    except Exception as e:
        expected = (type(e).__name__, str(e))
    if expected is None:
        getattr(fnx, cls)([(1, 2, [3])])
    else:
        with pytest.raises(getattr(fnx, expected[0], TypeError)):
            getattr(fnx, cls)([(1, 2, [3])])


# br-r37-c1-832s6: fewer than 8 plain pairs go straight to the class's native
# add_edge, and the replay for a bunch touching an existing edge shares that
# helper. For a pair networkx's add_edges_from is add_edge(u, v, **attr), so
# both must match it - including attrs named like add_edge's own parameters,
# which cannot travel as keywords (main raised TypeError onto an existing edge).
TINY_CASES = [
    ("pair", [(1, 2)], {}),
    ("pairs with attr", [(1, 2), (2, 3)], {"weight": 2}),
    ("existing edge twice", [(1, 2), (1, 2)], {"c": 1}),
    ("none v", [(5, 6), (3, None)], {}),
    ("none u", [(None, 1)], {}),
    ("unhashable v", [(5, 6), (3, [4])], {}),
    ("unhashable v, big bunch", [(i, i + 1) for i in range(10, 20)] + [(3, [4])], {}),
    ("self loop", [(1, 1)], {}),
    ("tuple bunch", ((1, 2), (2, 3)), {"w": 1}),
    ("u_of_edge onto existing", [(1, 2)], {"u_of_edge": 5}),
    ("v_of_edge onto new", [(7, 8)], {"v_of_edge": 5}),
    ("u_of_edge, big bunch onto existing", [(1, 2)] + [(i, i + 1) for i in range(10, 20)], {"u_of_edge": 5}),
]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
@pytest.mark.parametrize("label,bunch,attr", TINY_CASES, ids=[c[0] for c in TINY_CASES])
def test_small_plain_pair_bunch_matches_networkx(cls, label, bunch, attr):
    states = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls)()
        graph.add_edge(1, 2, w=0)
        try:
            graph.add_edges_from(bunch, **attr)
            error = None
        except Exception as exc:  # noqa: BLE001 - the exception is part of the state
            error = (type(exc).__name__, str(exc))
        states.append((error, [repr(n) for n in graph], sorted(map(repr, graph.edges(data=True)))))
    assert states[1] == states[0]


@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_add_edges_from_does_not_call_an_overridden_add_edge(cls):
    calls = []

    def make(base):
        class Recording(base):
            def add_edge(self, u, v, **attr):
                calls.append((base.__module__, u, v))
                super().add_edge(u, v, **attr)

        return Recording

    for lib in (nx, fnx):
        graph = make(getattr(lib, cls))()
        graph.add_edges_from([(1, 2), (2, 3)])
        graph.add_edges_from([(1, 2)])  # the existing-edge replay
        graph.add_edges_from([(1, 2)] + [(i, i + 1) for i in range(10, 20)])
    assert calls == []
