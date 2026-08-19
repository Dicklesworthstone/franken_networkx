"""br-r37-c1-6r00i — the hazards the keyed-index lookaside must survive.

`G[u][v][key]` on a multigraph reaches its edge attr dict through
`MultiKeyDictView.__getitem__`, which was the THIRD route to that dict and the
one left behind: `cached_keyed_edge_attrs_by_index` shipped with br-r37-c1-f3i50
and was wired into `get_edge_data(u, v, k)` and `G.edges[u, v, k]`, never here.
Everything on the old path was O(node key length) — `resolve_internal_edge_key`
hashes both endpoints, `PyGraph::edge_key` CLONES both into a
`(String, String, usize)`, and the `edge_py_attrs` probe hashes that tuple twice
(`contains_key` then `get`). Measured on a held cell, MultiGraph:

    cell[0]  K=3     275.3 ns   networkx  63.9 ns   0.2322x
    cell[0]  K=2000 1896.9 ns   networkx  61.6 ns   0.0325x

networkx is FLAT across a 667x span in key length and fnx was not.

WHAT MAKES THE FAST PATH SOUND, and therefore what this file pins:

  * THE nodes_seq STAMP IS LOAD-BEARING, and not merely as a cache-miss
    optimisation. Node removal RENUMBERS positions, so an unstamped entry does
    not miss — it names a DIFFERENT PAIR OF NODES and hands back another edge's
    live attr dict. `test_stale_positions_do_not_serve_another_edges_dict`
    reproduces exactly that, and getting there took two attempts: renumbering
    ALONE does not do it, because a stale cell probes its OLD positions and the
    entry filed there is still its own. The decoy has to be READ after the
    renumber, which re-files that entry. Verified against a deliberately
    unstamped negative-control build, which then serves edge (xx, yy)'s
    attributes for a read of edge (uu, vv). The first version of that test
    passed on the unstamped build and was therefore worthless.
  * THE ENTRY IS ORDER-NORMALISED, because this graph is undirected and u-v and
    v-u are one edge. Without it `G[v][u][k]` would miss an entry `G[u][v][k]`
    filled, and worse, could fill a second entry that later disagrees.
  * A HIT IS EXISTENCE PROOF. Entries are recorded only for edges that were
    present and `bump_edges_seq` clears the map on any edge mutation, so a
    removed edge cannot be served from it.
  * IDENTITY IS THE CONTRACT, not equality. The lookaside must hand back the
    SAME dict object the string-keyed mirror does, or a mutation through one
    handle is invisible through the other.

Everything else — non-int keys, remapped int keys, missing keys — must fall
through completely unchanged, and is asserted against networkx rather than
against a remembered shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))

import franken_networkx as fnx  # noqa: E402

MULTI_CLASSES = ("MultiGraph", "MultiDiGraph")


def _pair(cls_name="MultiGraph", *, keylen=2):
    """One graph per library.

    The padding nodes are not decoration: they are what makes a later
    `remove_node` renumber the probed pair's positions onto the (xx, yy) pair,
    which is the whole point of the stamp test below.
    """
    u, v = "u" * keylen, "v" * keylen
    x, y = "x" * keylen, "y" * keylen
    out = []
    for module in (nx, fnx):
        graph = getattr(module, cls_name)()
        for i in range(6):
            graph.add_node(f"pad{i}")
        graph.add_edge(u, v, w=1)
        graph.add_edge(u, v, w=2)
        graph.add_edge(x, y, w=3)
        out.append(graph)
    return out[0], out[1], u, v, x, y


# ---------------------------------------------------------------------------
# 1. the stamp
# ---------------------------------------------------------------------------
def test_stale_positions_do_not_serve_another_edges_dict():
    """The negative case the whole fast path stands on, in its exact shape.

    RENUMBERING ALONE IS NOT ENOUGH, and finding that out is the point of this
    test. A first attempt just removed nodes and re-read the stale cell — and it
    PASSED on a build with the stamp comparison removed, because the stale cell
    probes its OLD positions and the entry filed under those positions still
    belongs to it. A guard test that passes on the unguarded build is worthless,
    so the sequence had to be sharpened until it actually reproduced:

      1. warm the lookaside for (uu, vv), whose positions are (6, 7);
      2. remove two ISOLATED padding nodes — this renumbers so that the DECOY
         pair (xx, yy) moves onto positions (6, 7), and crucially does NOT bump
         `edges_seq`, so the lookaside is not cleared;
      3. read the DECOY through a fresh cell, which re-files entry (6, 7, 0)
         with the decoy's dict;
      4. read the stale cell again — it probes (6, 7, 0).

    On a build with the stamp removed, step 4 returns {'w': 3}: edge (xx, yy)'s
    live attribute dict, for a read of edge (uu, vv). Measured, not reasoned —
    a negative-control binary was built for exactly this and it serves the wrong
    edge. With the stamp, step 4 misses and falls back to the string path.
    """
    for module, expected in ((nx, {"w": 1}), (fnx, {"w": 1})):
        graph = module.MultiGraph()
        for i in range(6):
            graph.add_node(f"pad{i}")
        graph.add_edge("uu", "vv", w=1)  # positions 6, 7
        graph.add_edge("xx", "yy", w=3)  # positions 8, 9

        stale = graph["uu"]["vv"]
        assert dict(stale[0]) == expected

        graph.remove_node("pad0")
        graph.remove_node("pad1")  # uu=4 vv=5 xx=6 yy=7, edges_seq unchanged

        decoy = graph["xx"]["yy"]
        assert dict(decoy[0]) == {"w": 3}

        assert dict(stale[0]) == expected, (
            f"{module.__name__}: a stale cell was served the DECOY edge's attr "
            "dict — the nodes_seq stamp on the keyed index lookaside is not "
            "holding, and this is a wrong VALUE, not an error"
        )
        assert stale[0] is graph.get_edge_data("uu", "vv", 0)


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_node_removal_keeps_the_cell_matching_networkx(cls_name):
    """The plainer renumbering case, kept because it is the common one."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]
    assert dict(cell_fnx[0]) == dict(cell_nx[0]) == {"w": 1}

    for graph in (graph_nx, graph_fnx):
        graph.remove_node("pad0")
        graph.remove_node("pad1")

    assert dict(cell_fnx[0]) == dict(cell_nx[0])
    assert sorted(cell_fnx) == sorted(cell_nx)
    assert graph_fnx.get_edge_data(_x, _y, 0) == graph_nx.get_edge_data(_x, _y, 0)


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_reads_after_node_removal_keep_matching_networkx(cls_name):
    """Repeated reads either side of a renumber, so a stale refill is caught."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]
    for round_index in range(3):
        for key in sorted(cell_nx):
            assert dict(cell_fnx[key]) == dict(cell_nx[key]), (round_index, key)
        if round_index < 2:
            for graph in (graph_nx, graph_fnx):
                graph.remove_node(f"pad{round_index + 2}")


# ---------------------------------------------------------------------------
# 2. undirected order normalisation
# ---------------------------------------------------------------------------
def test_both_orientations_reach_the_same_dict_on_an_undirected_multigraph():
    """u-v and v-u are ONE edge, so both spellings must share the entry."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair("MultiGraph")
    for graph in (graph_nx, graph_fnx):
        assert graph[u][v][0] is graph[v][u][0]
    graph_fnx[v][u][0]["w"] = 31337
    graph_nx[v][u][0]["w"] = 31337
    assert graph_fnx.get_edge_data(u, v, 0) == graph_nx.get_edge_data(u, v, 0)
    assert dict(graph_fnx[u][v][0]) == dict(graph_nx[u][v][0])


def test_directed_multigraph_keeps_the_two_orientations_apart():
    """The directed class must NOT normalise — (u,v) and (v,u) are two edges."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair("MultiDiGraph")
    for graph in (graph_nx, graph_fnx):
        graph.add_edge(v, u, w=9)
    assert dict(graph_fnx[u][v][0]) == dict(graph_nx[u][v][0]) == {"w": 1}
    assert dict(graph_fnx[v][u][0]) == dict(graph_nx[v][u][0]) == {"w": 9}


# ---------------------------------------------------------------------------
# 3. a hit is existence proof
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_removed_edge_is_not_served_from_the_lookaside(cls_name):
    """`bump_edges_seq` clears the map; a warm entry must not outlive its edge."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]
    assert dict(cell_fnx[0]) == dict(cell_nx[0])

    for graph in (graph_nx, graph_fnx):
        graph.remove_edge(u, v, 0)

    for cell, name in ((cell_nx, "nx"), (cell_fnx, "fnx")):
        with pytest.raises(KeyError):
            cell[0]
    assert sorted(cell_fnx) == sorted(cell_nx)

    # A NEW edge takes a fresh key, and reading it must not serve the dead one.
    for graph in (graph_nx, graph_fnx):
        graph.add_edge(u, v, w=77)
    assert {k: dict(d) for k, d in cell_fnx.items()} == {
        k: dict(d) for k, d in cell_nx.items()
    }


# ---------------------------------------------------------------------------
# 4. identity, which is what makes the two mirrors interchangeable
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_lookaside_returns_the_same_object_as_every_other_route(cls_name):
    """Four spellings, one dict. Equality here would not catch a second copy."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name)
    for graph in (graph_nx, graph_fnx):
        cell = graph[u][v]
        first = cell[0]
        assert cell[0] is first, "repeat read handed back a different object"
        assert graph.get_edge_data(u, v, 0) is first
        assert graph.edges[u, v, 0] is first
        assert graph.adj[u][v][0] is first


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_mutation_through_the_lookaside_dict_reaches_the_graph(cls_name):
    """The binding constraint: a warm read must still be a LIVE handle."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name)
    for graph in (graph_nx, graph_fnx):
        cell = graph[u][v]
        cell[0]  # warm
        cell[0]["w"] = 4242
        cell[0]["fresh"] = True
    assert graph_fnx.get_edge_data(u, v, 0) == graph_nx.get_edge_data(u, v, 0)
    assert graph_fnx.get_edge_data(u, v, 0) == {"w": 4242, "fresh": True}


# ---------------------------------------------------------------------------
# 5. everything the probe must decline
# ---------------------------------------------------------------------------
def test_remapped_string_edge_keys_fall_through():
    """`has_remapped_int_key` disables the probe; both key spaces must work.

    With a string edge key in play the public key is no longer the internal one,
    so the gate that says "an exact PyInt IS the internal key" stops holding and
    the probe must decline. If it did not, `c[0]` would answer for whichever
    edge happens to sit at internal key 0.
    """
    for module in (nx, fnx):
        graph = module.MultiGraph()
        graph.add_edge("uu", "vv", key="alpha", w=1)
        graph.add_edge("uu", "vv", key=0, w=2)
        cell = graph["uu"]["vv"]
        assert dict(cell["alpha"]) == {"w": 1}
        assert dict(cell[0]) == {"w": 2}
        assert sorted(map(str, cell)) == ["0", "alpha"]


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
@pytest.mark.parametrize("probe", [99, "nope", 1.5, None, -1, True])
def test_non_matching_keys_raise_exactly_what_networkx_raises(cls_name, probe):
    """The declined shapes, asserted against networkx's own exception args."""
    graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name)
    cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]
    cell_nx[0], cell_fnx[0]  # warm both, so the probe is live

    nx_exc = fnx_exc = None
    try:
        got_nx = cell_nx[probe]
    except Exception as exc:  # noqa: BLE001 - the comparison IS the assertion
        nx_exc = (type(exc).__name__, exc.args)
        got_nx = None
    try:
        got_fnx = cell_fnx[probe]
    except Exception as exc:  # noqa: BLE001
        fnx_exc = (type(exc).__name__, exc.args)
        got_fnx = None

    assert fnx_exc == nx_exc
    if nx_exc is None:
        assert dict(got_fnx) == dict(got_nx)


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_long_node_keys_behave_exactly_as_short_ones(cls_name):
    """The lookaside exists to make this row flat in key length, not different."""
    for keylen in (2, 2000):
        graph_nx, graph_fnx, u, v, _x, _y = _pair(cls_name, keylen=keylen)
        cell_nx, cell_fnx = graph_nx[u][v], graph_fnx[u][v]
        for key in sorted(cell_nx):
            assert dict(cell_fnx[key]) == dict(cell_nx[key]), (keylen, key)
        assert sorted(cell_fnx) == sorted(cell_nx)
        assert cell_fnx[0] is graph_fnx.get_edge_data(u, v, 0)
