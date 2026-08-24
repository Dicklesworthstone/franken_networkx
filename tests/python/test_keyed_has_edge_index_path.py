"""br-r37-c1-s8dj1 — the KEYED has_edge index path must agree with the string path.

`PyMultiGraph::has_edge` had an O(1) route only while `key` was `None`: both fast
paths were gated on `key.is_none()`. Measured on the same function, the 2-arg
form is FLAT in node key length (181.2 ns at K=2, 175.6 ns at K=2000) while the
3-arg form grew 3.6x (360.5 ns to 1303.2 ns). That slope is the whole of
`(u, v) in G.edges` — the worst cell on the surface at 0.1322x against networkx —
because the shim's `_MultiGraphEdgeView.__contains__` routes here with key 0.

The new path resolves both endpoints to POSITIONS through CPython's cached `str`
hash and reaches the edge by `edge_attrs_by_indices`, skipping both canonicals.

WHAT THIS GUARDS, in order of how badly each would fail silently:

  1. THE TWO INDEX SPACES. Positions are converted to SLOTS inside
     `edge_attrs_by_indices`. Handing a position straight to the slot-keyed store
     reports a real edge as ABSENT after any node removal — a wrong answer on an
     ordinary read. The removal cases below exist for this and nothing else.
  2. THE GATE. The path is taken only for exact `str` endpoints with an exact
     `int` key on a graph whose display keys are pristine. Remapped keys, string
     keys, float keys, bool keys, negative keys and non-string endpoints must all
     keep the previous behaviour exactly.
  3. KEY IDENTITY. A 2-element membership test means key ZERO, not "any key"
     (br-r37-c1-6fs77). An edge added with `key='x'` must NOT answer True for
     `('a','b')`, and the fast path must not weaken that into a pair-existence
     check.

Every assertion compares against live networkx.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

MULTI = ["MultiGraph", "MultiDiGraph"]
LONG = "z" * 2000


def _pair(cls_name):
    return getattr(nx, cls_name)(), getattr(fnx, cls_name)()


def _same_has_edge(gnx, gfx, u, v, key):
    want = gnx.has_edge(u, v, key) if key is not None else gnx.has_edge(u, v)
    got = gfx.has_edge(u, v, key) if key is not None else gfx.has_edge(u, v)
    return got == want, want, got


# ------------------------------------------------------------- the happy path


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize("key_len", [2, len(LONG)])
def test_keyed_has_edge_matches_networkx(cls_name, key_len):
    u, v, w = ("u" * key_len, "v" * key_len, "w" * key_len)
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge(u, v, weight=1.0)
        g.add_edge(u, v, weight=2.0)
        g.add_edge(v, w, weight=3.0)
    for a, b in [(u, v), (v, u), (v, w), (u, w), (u, "absent")]:
        for key in (0, 1, 2, 7):
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"{cls_name} has_edge({a[:3]}..,{b[:3]}..,{key}) nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_edges_membership_matches_networkx(cls_name):
    """The caller this fix exists for."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("a", "b", weight=2.0)
        g.add_edge("b", "c", weight=3.0)
    for probe in [("a", "b"), ("b", "a"), ("a", "b", 0), ("a", "b", 1),
                  ("a", "b", 5), ("a", "zz"), ("zz", "a"), ("b", "c", 0)]:
        assert (probe in gfx.edges) == (probe in gnx.edges), probe


# -------------------------------------------------- the two index spaces (1)


@pytest.mark.parametrize("cls_name", MULTI)
def test_keyed_has_edge_after_node_removal_renumbers_positions(cls_name):
    """THE hazard. Removing an earlier node shifts every later POSITION down,
    while the store is keyed by SLOT. If the conversion is skipped, a real edge
    reports absent."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        for n in ("n0", "n1", "n2", "n3", "n4"):
            g.add_node(n)
        g.add_edge("n2", "n3", weight=1.0)
        g.add_edge("n2", "n3", weight=2.0)
        g.add_edge("n1", "n4", weight=3.0)
    assert _same_has_edge(gnx, gfx, "n2", "n3", 0)[0]

    for g in (gnx, gfx):
        g.remove_node("n0")
    for a, b in [("n2", "n3"), ("n1", "n4"), ("n3", "n2")]:
        for key in (0, 1):
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"after removal {a},{b},{key}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_keyed_has_edge_after_removal_and_readd(cls_name):
    """A re-add reuses a slot; positions move again."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("c", "d", weight=2.0)
        g.remove_node("a")
        g.add_edge("e", "d", weight=3.0)
        g.add_edge("a", "d", weight=4.0)
    for a, b in [("a", "d"), ("c", "d"), ("e", "d"), ("a", "b")]:
        ok, want, got = _same_has_edge(gnx, gfx, a, b, 0)
        assert ok, f"{a},{b}: nx={want} fnx={got}"


# --------------------------------------------------------------- the gate (2)


@pytest.mark.parametrize("cls_name", MULTI)
def test_non_integer_and_remapped_keys_keep_the_string_path(cls_name):
    """String, float and bool keys, and a graph with a REMAPPED display key,
    are all excluded from the fast path and must be unchanged."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", key="x", weight=1.0)
        g.add_edge("a", "b", key=5, weight=2.0)
        g.add_edge("c", "d", weight=3.0)
    for key in ("x", 5, 0, 1, 2.0, True, False, -1, "0"):
        for a, b in [("a", "b"), ("c", "d")]:
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"{cls_name} key={key!r} on {a},{b}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_non_string_endpoints_keep_the_string_path(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge(1, 2, weight=1.0)
        g.add_edge(1, 2, weight=2.0)
        g.add_edge((3, 4), 5, weight=3.0)
    for a, b in [(1, 2), (2, 1), ((3, 4), 5), (1, 9)]:
        for key in (0, 1):
            ok, want, got = _same_has_edge(gnx, gfx, a, b, key)
            assert ok, f"{a!r},{b!r},{key}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_absent_endpoint_answers_false_without_raising(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
    for a, b in [("missing", "b"), ("a", "missing"), ("missing", "other")]:
        ok, want, got = _same_has_edge(gnx, gfx, a, b, 0)
        assert ok and got is False, f"{a},{b}: nx={want} fnx={got}"


# ------------------------------------------------------------ key identity (3)


@pytest.mark.parametrize("cls_name", MULTI)
def test_key_zero_is_not_any_key(cls_name):
    """br-r37-c1-6fs77: a 2-element membership test means key ZERO. An edge
    whose only key is 'x' must not answer True — the fast path must not decay
    into a pair-existence check."""
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", key="x", weight=1.0)
    assert (("a", "b") in gfx.edges) == (("a", "b") in gnx.edges) is False
    assert gfx.has_edge("a", "b", 0) == gnx.has_edge("a", "b", 0) is False
    assert gfx.has_edge("a", "b", "x") == gnx.has_edge("a", "b", "x") is True
    assert gfx.has_edge("a", "b") == gnx.has_edge("a", "b") is True


@pytest.mark.parametrize("cls_name", MULTI)
def test_removed_key_stops_answering_true(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=1.0)
        g.add_edge("a", "b", weight=2.0)
    assert _same_has_edge(gnx, gfx, "a", "b", 1)[0]
    for g in (gnx, gfx):
        g.remove_edge("a", "b", 1)
    for key in (0, 1):
        ok, want, got = _same_has_edge(gnx, gfx, "a", "b", key)
        assert ok, f"after remove_edge key={key}: nx={want} fnx={got}"


@pytest.mark.parametrize("cls_name", MULTI)
def test_direction_is_preserved_on_the_directed_class(cls_name):
    gnx, gfx = _pair(cls_name)
    for g in (gnx, gfx):
        g.add_edge("src", "dst", weight=1.0)
    for a, b in [("src", "dst"), ("dst", "src")]:
        ok, want, got = _same_has_edge(gnx, gfx, a, b, 0)
        assert ok, f"{a}->{b}: nx={want} fnx={got}"
    if cls_name == "MultiDiGraph":
        assert gnx.has_edge("dst", "src", 0) is False, "networkx oracle changed"


# ------------------------------------------- the directed lookaside (2026-08-24)
#
# MultiDiGraph reached the keyed path through a lookaside that did not exist when
# the tests above were written: `MultiDiGraph::edge_pair_index`, a (source
# position, target position) -> edges-position map. Everything below exercises
# the MACHINERY rather than the answer, because the answer is already covered and
# a stale lookaside gives a WRONG one silently.
#
# Three properties, and each has a way to fail on its own:
#
#   * it is built only after a warm-up, so results must not depend on whether it
#     is built -- a first attempt rebuilt on every mutation and measured 137x
#     slower than networkx on an add-then-check loop, which is why the guard and
#     the incremental patches exist at all;
#   * adds PATCH it in place (insert appends, so nothing moves), and a removal
#     that empties a bucket SWAP-removes, relocating exactly one other entry;
#   * `remove_node` renumbers `nodes` wholesale, so it deliberately does NOT
#     patch and must fall back to a rebuild.

WARMUP_PROBES = 200  # comfortably past the floor for the small fixtures here


def _force_index(graph, u, v):
    """Probe until the lookaside is certainly built for this revision."""
    for _ in range(WARMUP_PROBES):
        graph.has_edge(u, v, 0)


def _all_pairs_agree(gnx, gfx, nodes):
    for a in nodes:
        for b in nodes:
            assert gfx.has_edge(a, b) == gnx.has_edge(a, b), (a, b)
            assert ((a, b) in gfx.edges) == ((a, b) in gnx.edges), (a, b)
            for key in (0, 1):
                assert gfx.has_edge(a, b, key) == gnx.has_edge(a, b, key), (a, b, key)


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_answer_does_not_depend_on_whether_the_lookaside_is_built(cls_name):
    """Below the warm-up the string path answers; above it the index does."""
    gnx, gfx = _pair(cls_name)
    for i in range(6):
        gnx.add_edge(f"n{i}", f"n{i + 1}")
        gfx.add_edge(f"n{i}", f"n{i + 1}")
    nodes = [f"n{i}" for i in range(8)]

    _all_pairs_agree(gnx, gfx, nodes)  # cold: no index yet
    _force_index(gfx, "n0", "n1")
    _all_pairs_agree(gnx, gfx, nodes)  # warm: answered from the index


@pytest.mark.parametrize("cls_name", MULTI)
def test_an_add_after_the_index_is_built_is_visible(cls_name):
    """The incremental patch: an add must not need a rebuild to be seen."""
    gnx, gfx = _pair(cls_name)
    for i in range(6):
        gnx.add_edge(f"n{i}", f"n{i + 1}")
        gfx.add_edge(f"n{i}", f"n{i + 1}")
    _force_index(gfx, "n0", "n1")

    for graph in (gnx, gfx):
        graph.add_edge("fresh", "target")          # both endpoints new
        graph.add_edge("n0", "n5")                 # new pair, existing nodes
        graph.add_edge("n0", "n1", key=7)          # parallel key on an old pair

    nodes = [f"n{i}" for i in range(8)] + ["fresh", "target"]
    _all_pairs_agree(gnx, gfx, nodes)
    assert gfx.has_edge("n0", "n1", 7) is True
    assert gfx.has_edge("fresh", "target") is True


@pytest.mark.parametrize("cls_name", MULTI)
def test_a_removal_that_relocates_another_bucket_is_visible(cls_name):
    """THE swap-remove case: emptying a bucket moves the LAST one into its slot.

    Patching only the removed pair would leave the relocated pair pointing at the
    wrong position -- which reads as a real edge reported absent, or worse, one
    pair answering with another's attributes.
    """
    gnx, gfx = _pair(cls_name)
    pairs = [(f"a{i}", f"b{i}") for i in range(6)]
    for u, v in pairs:
        gnx.add_edge(u, v)
        gfx.add_edge(u, v)
    _force_index(gfx, *pairs[0])

    for graph in (gnx, gfx):
        graph.remove_edge(*pairs[1])  # NOT the last bucket, so another relocates

    nodes = [n for pair in pairs for n in pair]
    _all_pairs_agree(gnx, gfx, nodes)
    assert gfx.has_edge(*pairs[5]) is True, "the relocated bucket went missing"
    assert gfx.has_edge(*pairs[1]) is False


@pytest.mark.parametrize("cls_name", MULTI)
def test_node_removal_after_the_index_is_built_renumbers_correctly(cls_name):
    """`remove_node` shifts every later node position, so the map must be dropped."""
    gnx, gfx = _pair(cls_name)
    for i in range(6):
        gnx.add_edge(f"n{i}", f"n{i + 1}")
        gfx.add_edge(f"n{i}", f"n{i + 1}")
    _force_index(gfx, "n0", "n1")

    for graph in (gnx, gfx):
        graph.remove_node("n2")

    nodes = [f"n{i}" for i in range(8)]
    _all_pairs_agree(gnx, gfx, nodes)

    for graph in (gnx, gfx):
        graph.add_edge("n2", "n6")
    _all_pairs_agree(gnx, gfx, nodes)


@pytest.mark.parametrize("cls_name", MULTI)
def test_a_copy_does_not_inherit_the_originals_lookaside(cls_name):
    """The cache clones COLD.

    Sharing it would let two graphs whose revisions advance independently -- and
    can coincide -- read each other's map. The copy is mutated here and the
    original re-read, which is the direction that would show it.
    """
    gnx, gfx = _pair(cls_name)
    for i in range(6):
        gnx.add_edge(f"n{i}", f"n{i + 1}")
        gfx.add_edge(f"n{i}", f"n{i + 1}")
    _force_index(gfx, "n0", "n1")

    copy_nx, copy_fx = gnx.copy(), gfx.copy()
    for graph in (copy_nx, copy_fx):
        graph.add_edge("only", "inthecopy")
        graph.remove_edge("n0", "n1")

    nodes = [f"n{i}" for i in range(8)] + ["only", "inthecopy"]
    _all_pairs_agree(gnx, gfx, nodes)          # the ORIGINAL is untouched
    _all_pairs_agree(copy_nx, copy_fx, nodes)  # and the copy is right too
    assert gfx.has_edge("n0", "n1") is True
    assert copy_fx.has_edge("n0", "n1") is False


MUTATION_SEQUENCES = [
    ("add then remove then add", [("add", "x", "y"), ("del", "x", "y"), ("add", "x", "y")]),
    ("remove first bucket", [("del", "a0", "b0"), ("add", "a9", "b9")]),
    ("remove last bucket", [("del", "a4", "b4"), ("add", "a9", "b9")]),
    ("drop a node then rebuild it", [("delnode", "a2", None), ("add", "a2", "b2")]),
    ("clear the edges then re-add", [("clear", None, None), ("add", "a0", "b0")]),
    ("parallel key then drop one", [("addkey", "a0", "b0"), ("del", "a0", "b0")]),
]


@pytest.mark.parametrize("cls_name", MULTI)
@pytest.mark.parametrize(
    "label,steps", MUTATION_SEQUENCES, ids=[s[0] for s in MUTATION_SEQUENCES]
)
def test_mutation_interleavings_agree_with_networkx_at_every_step(cls_name, label, steps):
    """The matrix, not a spot check: the index is built FIRST, then mutated
    through, and every pair is compared after every single step."""
    gnx, gfx = _pair(cls_name)
    pairs = [(f"a{i}", f"b{i}") for i in range(5)]
    for u, v in pairs:
        gnx.add_edge(u, v)
        gfx.add_edge(u, v)
    _force_index(gfx, *pairs[0])

    nodes = [n for pair in pairs for n in pair] + ["x", "y", "a9", "b9"]
    for op, u, v in steps:
        for graph in (gnx, gfx):
            if op == "add":
                graph.add_edge(u, v)
            elif op == "addkey":
                graph.add_edge(u, v, key=3)
            elif op == "del":
                if graph.has_edge(u, v):
                    graph.remove_edge(u, v)
            elif op == "delnode":
                if graph.has_node(u):
                    graph.remove_node(u)
            elif op == "clear":
                graph.clear_edges()
        _all_pairs_agree(gnx, gfx, nodes), label
