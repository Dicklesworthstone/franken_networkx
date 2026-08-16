"""br-r37-c1-f3i50 — the keydict index lookaside must invalidate on EDGE mutation.

`MultiDiGraph.get_edge_data(u, v)` is served from a keydict cache. That cache
removed the O(parallel edges) rebuild, but it is keyed by canonical STRINGS, so
even a HIT costs two canonicalisations and two full-length hashes — the entire
remaining key-length slope, certified at 0.0735x against networkx with
2000-character keys (81.8 ns to 1111.7 ns).

The fix adds an endpoint-INDEX twin holding the same mapping, probed before any
canonical is built.

THIS FILE EXISTS BECAUSE THE FIRST ATTEMPT WAS WRONG IN A SILENT WAY. It stamped
entries with `nodes_seq` alone. An edge mutation bumps `edges_seq` and leaves
`nodes_seq` untouched, so a warm `get_edge_data` followed by `add_edge` kept
serving the OLD keydict — a wrong answer, not a crash, on a read that looks
entirely ordinary. The string-keyed cache it mirrors is generation-checked on
BOTH sequences at read time; the twin must be too.

Every case below warms the cache FIRST and then mutates, because a cold read
cannot expose a stale-cache bug. Correctness is asserted against live networkx
rather than against a remembered value, so the tests stay honest if the
underlying semantics ever change.
"""

from __future__ import annotations

import networkx as nx
import pytest

CLASSES = ["MultiGraph", "MultiDiGraph"]
LONG = "z" * 300


def _pair(cls_name, parallel=2, key_len=1):
    import franken_networkx as fnx

    u = "a".ljust(key_len, "q")
    v = "b".ljust(key_len, "q")
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        for k in range(parallel):
            graph.add_edge(u, v, weight=float(k))
        graph.add_edge(v, "c", weight=9.0)
    return gnx, gfx, u, v


def _same(gnx, gfx, u, v):
    """Value-and-order comparison of the returned keydict against networkx."""
    want, got = gnx.get_edge_data(u, v), gfx.get_edge_data(u, v)
    if want is None or got is None:
        return want is None and got is None
    return list(got) == list(want) and {k: dict(d) for k, d in got.items()} == {
        k: dict(d) for k, d in want.items()
    }


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_len", [1, len(LONG)])
def test_warm_read_then_add_parallel_edge(cls_name, key_len):
    """THE regression. Warm, add an edge, re-read — a stale cache answers old.

    Long keys are parametrised because the index probe is exact-`str` gated and
    only engages for string endpoints; the short case proves the fix did not
    make the short path wrong on the way past.
    """
    gnx, gfx, u, v = _pair(cls_name, key_len=key_len)
    assert _same(gnx, gfx, u, v)  # warm both
    for graph in (gnx, gfx):
        graph.add_edge(u, v, weight=99.0)
    assert _same(gnx, gfx, u, v), "stale keydict after add_edge"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_read_then_remove_one_parallel_edge(cls_name):
    gnx, gfx, u, v = _pair(cls_name, parallel=3)
    assert _same(gnx, gfx, u, v)
    for graph in (gnx, gfx):
        graph.remove_edge(u, v)
    assert _same(gnx, gfx, u, v), "stale keydict after remove_edge"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_read_then_remove_all_edges_between_the_pair(cls_name):
    """Once the last parallel edge goes the answer becomes None, not a mapping."""
    gnx, gfx, u, v = _pair(cls_name, parallel=2)
    assert _same(gnx, gfx, u, v)
    for graph in (gnx, gfx):
        graph.remove_edge(u, v)
        graph.remove_edge(u, v)
    assert gfx.get_edge_data(u, v) is None
    assert _same(gnx, gfx, u, v)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_read_then_node_removal_renumbers_indices(cls_name):
    """The `nodes_seq` half. Removing an EARLIER node renumbers every later index.

    An entry keyed by a bare index pair would resolve to a DIFFERENT edge after
    this, which is why the stamp carries `nodes_seq` as well as `edges_seq`.
    """
    import franken_networkx as fnx

    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("n0", "n1", tag="first")
        graph.add_edge("n2", "n3", tag="late")
        graph.add_edge("n2", "n3", tag="late2")
    assert _same(gnx, gfx, "n2", "n3")  # warm the late pair
    for graph in (gnx, gfx):
        graph.remove_node("n0")
    assert _same(gnx, gfx, "n2", "n3"), "index resolved to the wrong edge after renumbering"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_warm_read_then_attribute_mutation_is_visible(cls_name):
    """Attr edits do not bump either sequence; the values are live dicts."""
    gnx, gfx, u, v = _pair(cls_name)
    assert _same(gnx, gfx, u, v)
    for graph in (gnx, gfx):
        graph[u][v][0]["weight"] = 42.0
    assert _same(gnx, gfx, u, v), "attribute edit invisible through the cache"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_the_returned_mapping_is_a_copy_not_the_cache(cls_name):
    """Writing into the result must not corrupt what the next reader sees.

    The cache hands back a shallow COPY precisely so a caller's `d[k] = {}`
    cannot invent a key that `G.edges` does not have.
    """
    gnx, gfx, u, v = _pair(cls_name)
    got = gfx.get_edge_data(u, v)
    got[7] = {"weight": 7.0}
    assert 7 not in gfx.get_edge_data(u, v)
    assert _same(gnx, gfx, u, v)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_non_string_endpoints_still_correct(cls_name):
    """The probe is exact-`str` gated; other key types must be unaffected."""
    import franken_networkx as fnx

    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge(1, 2, weight=1.0)
        graph.add_edge(1, 2, weight=2.0)
    assert _same(gnx, gfx, 1, 2)
    for graph in (gnx, gfx):
        graph.add_edge(1, 2, weight=3.0)
    assert _same(gnx, gfx, 1, 2)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_absent_pairs_stay_absent_after_warming_a_neighbour(cls_name):
    """A warm entry for one pair must not answer for a different pair."""
    gnx, gfx, u, v = _pair(cls_name)
    assert _same(gnx, gfx, u, v)
    assert gfx.get_edge_data(u, "nowhere") is None
    assert gfx.get_edge_data("nowhere", v) is None
    assert _same(gnx, gfx, u, "nowhere")
