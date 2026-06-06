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
