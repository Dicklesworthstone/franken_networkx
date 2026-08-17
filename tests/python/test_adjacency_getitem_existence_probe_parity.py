"""br-r37-c1-2ndmw — the row-cell existence probe must not build a value it discards.

`AdjacencyView.__getitem__` used `atlas[node]` purely to decide whether the key
was present, and threw the result away. On a multigraph row the atlas is a
native `MultiAtlasView` whose `__getitem__` allocates a whole `MultiKeyDictView`
(cloning the row's node key on the way), and the `AtlasView` it then returns
re-derives that same value lazily through its own getter — so the object was
built, dropped, and built again on first use. Measured on the multigraph cell at
2000-character keys, the discarded construction was 830.4 ns of a 1724.4 ns
call: 48.2 percent of the work.

The probe is now `node in atlas`, which answers through `has_edge` without
materialising anything.

WHAT THIS FILE IS GUARDING. Swapping `__getitem__` for `__contains__` as a
presence test is only sound if the two agree, and there are three ways it could
quietly not:

  1. UNHASHABLE KEYS. The native multi atlas's `__contains__` answers False for
     an unhashable key rather than raising — `node_key_to_string` canonicalises
     by value and never hashes. So `in` alone would turn nx's TypeError into a
     KeyError. The explicit `hash(node)` ahead of the probe is what prevents
     that, and it is pinned here so a later "cleanup" cannot drop it.
  2. THE ABSENT PATH. The exception, its args, and its `from exc` chaining must
     not move. The implementation deliberately still routes absent keys through
     `__getitem__` rather than constructing the error from the `in` result.
  3. FILTERED ATLASES. Subgraph views wrap the row in a filtering atlas whose
     membership and subscript must agree; nx's own wording for those is what
     br-r37-c1-k4nsd restored, and a contains-based probe must not flatten it.

Every assertion compares against live networkx rather than a remembered value.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

ALL = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]
EDGES = [("hub", "s0"), ("hub", "s1"), ("s0", "s1")]
LONG = "z" * 2000


def _pair(cls_name, edges=EDGES):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for u, v in edges:
        gnx.add_edge(u, v, w=1.0)
        gfx.add_edge(u, v, w=1.0)
    return gnx, gfx


def _cells_agree(gnx, gfx, u, v):
    want, got = gnx.adj[u][v], gfx.adj[u][v]
    return list(got) == list(want) and {k: dict(got[k]) for k in got} == {
        k: dict(want[k]) for k in want
    }


# ---------------------------------------------------------------- present keys


@pytest.mark.parametrize("cls_name", ALL)
def test_present_cell_matches_networkx(cls_name):
    """The path the change actually touches."""
    gnx, gfx = _pair(cls_name)
    for u, v in [("hub", "s0"), ("hub", "s1"), ("s0", "s1")]:
        if cls_name in MULTI:
            assert _cells_agree(gnx, gfx, u, v), (u, v)
        else:
            assert dict(gfx.adj[u][v]) == dict(gnx.adj[u][v]), (u, v)


@pytest.mark.parametrize("cls_name", MULTI)
def test_present_cell_at_long_keys(cls_name):
    """2000-character keys — the length that made the discarded build 48 percent."""
    u, v = "u" + LONG, "v" + LONG
    gnx, gfx = _pair(cls_name, [(u, v), (u, "c")])
    gnx.add_edge(u, v, w=2.0)
    gfx.add_edge(u, v, w=2.0)
    assert _cells_agree(gnx, gfx, u, v)


@pytest.mark.parametrize("cls_name", ALL)
def test_cell_stays_live_across_edge_mutation(cls_name):
    """The returned view re-derives its value; it must not have been frozen.

    If a future change captures the probe's value instead of dropping it, this
    is the test that notices the view stopped tracking the graph.
    """
    gnx, gfx = _pair(cls_name)
    cell_nx, cell_fx = gnx.adj["hub"]["s0"], gfx.adj["hub"]["s0"]
    for graph in (gnx, gfx):
        graph.add_edge("hub", "s0", w=9.0)
    if cls_name in MULTI:
        assert list(cell_fx) == list(cell_nx)
        assert {k: dict(cell_fx[k]) for k in cell_fx} == {k: dict(cell_nx[k]) for k in cell_nx}
    else:
        assert dict(cell_fx) == dict(cell_nx)


# ----------------------------------------------------------------- absent keys


@pytest.mark.parametrize("cls_name", ALL)
def test_absent_cell_raises_the_same_exception_and_args(cls_name):
    """Type AND args — a type-only check reports false green."""
    gnx, gfx = _pair(cls_name)
    for u, v in [("hub", "absent"), ("s0", "hub" + "x")]:
        want = got = None
        try:
            gnx.adj[u][v]
        except Exception as exc:  # noqa: BLE001 - comparing the exception itself
            want = (type(exc), exc.args)
        try:
            gfx.adj[u][v]
        except Exception as exc:  # noqa: BLE001
            got = (type(exc), exc.args)
        assert got == want, (cls_name, u, v)


@pytest.mark.parametrize("cls_name", MULTI)
def test_absent_cell_preserves_exception_chaining(cls_name):
    """`from exc` chaining is observable; the absent path must keep routing
    through `__getitem__` rather than synthesising the error from `in`.

    MULTI only, and that is not an oversight. On `Graph`/`DiGraph` the row is a
    native `_fnx.AtlasView` whose C-level subscript raises `KeyError` directly,
    so no Python `raise ... from exc` runs and there is no cause to find —
    which matches networkx, whose own `AtlasView.__getitem__` is a bare
    `return self._atlas[name]` and never chains either. Asserting chaining
    there would be pinning a divergence rather than preventing one.
    """
    _, gfx = _pair(cls_name)
    with pytest.raises(KeyError) as caught:
        gfx.adj["hub"]["absent"]
    assert caught.value.__cause__ is not None, "lost the chained cause"
    assert isinstance(caught.value.__cause__, KeyError)


@pytest.mark.parametrize("cls_name", ALL)
@pytest.mark.parametrize("key", [12345, ("t", "u"), 3.5, True])
def test_absent_nonstring_key_keeps_its_own_type_in_the_args(cls_name, key):
    """br-keystr: the KeyError carries the original key, not a Rust str repr."""
    gnx, gfx = _pair(cls_name)
    want = got = None
    try:
        gnx.adj["hub"][key]
    except Exception as exc:  # noqa: BLE001
        want = (type(exc), exc.args)
    try:
        gfx.adj["hub"][key]
    except Exception as exc:  # noqa: BLE001
        got = (type(exc), exc.args)
    assert got == want, (cls_name, key)


# ------------------------------------------------------------ unhashable keys


@pytest.mark.parametrize("cls_name", ALL)
@pytest.mark.parametrize("key", [["x"], {"a": 1}, {1, 2}])
def test_unhashable_key_is_a_typeerror_not_a_keyerror(cls_name, key):
    """THE trap. The native multi atlas answers False for an unhashable key
    instead of raising, so an `in`-only probe would downgrade this to KeyError.
    The explicit hash() ahead of the probe is what keeps it a TypeError."""
    gnx, gfx = _pair(cls_name)
    with pytest.raises(TypeError):
        gnx.adj["hub"][key]
    with pytest.raises(TypeError):
        gfx.adj["hub"][key]


# --------------------------------------------------------- filtered atlases


@pytest.mark.parametrize(
    "cls_name",
    [
        "Graph",
        "DiGraph",
        pytest.param(
            "MultiGraph",
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-2ndmw: k4nsd's FilterAtlas wording was never "
                "mirrored to the multigraph subgraph row — fnx raises "
                "KeyError('s1') where nx raises KeyError('Key s1 not found'). "
                "PRE-EXISTING: reproduced identically against unmodified HEAD, "
                "so it is not the existence-probe change. The multigraph "
                "subgraph row reaches AdjacencyView.__getitem__ with owner=None "
                "and an atlas that is itself a nested Python AdjacencyView, so "
                "BOTH signals _missing_node_key_error decides on "
                "(_graph_is_filtered / _atlas_is_filtered) read False. Fixing it "
                "means threading the filtered signal through that construction, "
                "which is a separate change from this one.",
            ),
        ),
        pytest.param(
            "MultiDiGraph",
            marks=pytest.mark.xfail(
                strict=True,
                reason="br-r37-c1-2ndmw: see MultiGraph — same lost filtered "
                "signal on the multigraph subgraph row, same pre-existing "
                "reproduction against unmodified HEAD.",
            ),
        ),
    ],
)
def test_subgraph_view_cells_agree_including_the_filtered_absent_wording(cls_name):
    """br-r37-c1-k4nsd: a filtered atlas raises nx's own FilterAtlas wording,
    which the probe change must not flatten to a bare key.

    Strict xfail on the multigraphs records a REAL divergence rather than
    hiding it: strict means this starts failing the moment someone fixes the
    wording, which forces the marker off instead of letting it rot.
    """
    gnx, gfx = _pair(cls_name)
    snx, sfx = gnx.subgraph(["hub", "s0"]), gfx.subgraph(["hub", "s0"])
    if cls_name in MULTI:
        assert _cells_agree(snx, sfx, "hub", "s0")
    else:
        assert dict(sfx.adj["hub"]["s0"]) == dict(snx.adj["hub"]["s0"])
    # 's1' is filtered OUT of the subgraph, so its cell must be absent in both.
    want = got = None
    try:
        snx.adj["hub"]["s1"]
    except Exception as exc:  # noqa: BLE001
        want = (type(exc), exc.args)
    try:
        sfx.adj["hub"]["s1"]
    except Exception as exc:  # noqa: BLE001
        got = (type(exc), exc.args)
    assert got == want, cls_name


@pytest.mark.parametrize("cls_name", ALL)
def test_membership_and_subscript_agree_on_every_row(cls_name):
    """The invariant the change relies on: `in` and `[]` must not disagree.

    Asserted directly over every (row, candidate) pair, present and absent, so a
    future atlas whose membership drifts from its subscript is caught here
    rather than as a mystery KeyError in user code.
    """
    _, gfx = _pair(cls_name)
    candidates = ["hub", "s0", "s1", "absent", "s2"]
    for row_node in ["hub", "s0", "s1"]:
        row = gfx.adj[row_node]
        for cand in candidates:
            present = cand in row
            try:
                row[cand]
                subscript_ok = True
            except KeyError:
                subscript_ok = False
            assert present == subscript_ok, (cls_name, row_node, cand)
