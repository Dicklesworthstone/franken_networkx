"""br-r37-c1-ey6ob: view read probes canonicalize the key WITHOUT allocating.

The native view slots (`NodeView`, `EdgeView`, `DegreeView`, `AdjacencyView`,
`AtlasView`) used to call ``node_key_to_string`` on every membership test and
every subscript. That returns an OWNED ``String`` which the probe hashes once
and drops — a malloc/free per ``n in G.nodes()`` / ``G.nodes[n]`` /
``(u, v) in G.edges()`` / ``G.edges[u, v]`` / ``G.degree[n]`` / ``v in G[u]``,
against nx's zero. They now borrow the canonical out of a stack buffer
(``with_node_key_str`` / ``canonical_node_key_in``, br-r37-c1-oe93x).

THE NEGATIVE CASE THIS FILE EXISTS FOR. That stack buffer is
``CANONICAL_KEY_STACK_BUF = 128`` bytes and the canonical form is
``"str:{len}:{s}"``, so a key spills to the heap fallback at
``4 + len(str(n)) + 1 + n`` > 128 — i.e. at n = 121 for a three-digit length.
An implementation that wrote into the buffer without checking, or that
truncated instead of falling back, would silently ALIAS two long keys that
share a 128-byte prefix onto one canonical: distinct nodes would merge, edges
would move, and every read below would agree with itself while disagreeing
with nx. ``test_long_key_boundary_*`` straddles that branch on purpose (120 in
the buffer, 121 and 200 on the heap) with keys that differ only past the
boundary, so a truncating implementation fails rather than passing quietly.

The non-str keys matter for the same reason from the other side: they never
enter the buffer at all and must keep taking the owned build unchanged.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

# "str:{len}:{s}" must fit CANONICAL_KEY_STACK_BUF = 128 bytes.
# 4 + len("120") + 1 + 120 == 128 -> the last length served from the buffer.
KEY_IN_BUFFER = 120
KEY_OVER_BUFFER = 121


def _pair(n):
    """Two distinct length-*n* keys agreeing on their first 128 bytes."""
    return "x" * (n - 1) + "a", "x" * (n - 1) + "b"


def _both(build):
    """Run *build* against a fresh nx graph and a fresh fnx graph."""
    return build(nx.Graph()), build(fnx.Graph())


# ---------------------------------------------------------------------------
# The long-key boundary — the case a truncating implementation gets wrong.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("length", [8, KEY_IN_BUFFER, KEY_OVER_BUFFER, 200, 4096])
def test_long_key_boundary_keeps_prefix_sharing_keys_distinct(length):
    left, right = _pair(length)
    # The keys always differ in their LAST byte only. Once the canonical spills
    # past the 128-byte stack buffer that byte is beyond it, so a truncating
    # implementation would alias the pair — which is the case this asserts is
    # still distinguished.
    if length > 128:
        assert left[:128] == right[:128], "fixture must share the whole stack buffer"

    def build(g):
        g.add_edge(left, "hub")
        g.add_edge(right, "hub")
        return g

    ref, got = _both(build)

    assert got.number_of_nodes() == ref.number_of_nodes() == 3
    assert sorted(got.nodes()) == sorted(ref.nodes())
    # Membership through the native NodeView slot.
    assert (left in got.nodes()) is (left in ref.nodes()) is True
    assert (right in got.nodes()) is (right in ref.nodes()) is True
    # A key one byte longer than either is absent in both.
    assert (left + "z" in got.nodes()) is (left + "z" in ref.nodes()) is False


@pytest.mark.parametrize("length", [KEY_IN_BUFFER, KEY_OVER_BUFFER, 200])
def test_long_key_boundary_edge_probes_and_subscripts(length):
    left, right = _pair(length)

    def build(g):
        g.add_edge(left, "hub", weight=1)
        g.add_edge(right, "hub", weight=2)
        return g

    ref, got = _both(build)

    # EdgeView.__contains__ / __getitem__ (two borrowed endpoint canonicals).
    assert ((left, "hub") in got.edges()) is ((left, "hub") in ref.edges()) is True
    assert ((left, right) in got.edges()) is ((left, right) in ref.edges()) is False
    assert got.edges[left, "hub"] == ref.edges[left, "hub"] == {"weight": 1}
    assert got.edges[right, "hub"] == ref.edges[right, "hub"] == {"weight": 2}

    # AtlasView.__getitem__ / __contains__ and AdjacencyView.__contains__.
    assert got["hub"][left] == ref["hub"][left] == {"weight": 1}
    assert (left in got["hub"]) is (left in ref["hub"]) is True
    assert (left in got.adj) is (left in ref.adj) is True

    # DegreeView.__getitem__ and DegreeView.__call__(single node).
    assert got.degree[left] == ref.degree[left] == 1
    assert got.degree(left) == ref.degree(left) == 1
    assert got.degree["hub"] == ref.degree["hub"] == 2


# ---------------------------------------------------------------------------
# Key shapes that never enter the stack buffer must be unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        7,
        -7,
        0,
        True,
        3.5,
        2.0,
        (1, 2),
        ("a", 1),
        2**63 + 7,
        -(2**70),
        "",
        "unicode-é中文",
    ],
    ids=repr,
)
def test_non_str_and_exotic_keys_probe_identically(key):
    def build(g):
        g.add_edge(key, "hub", weight=9)
        return g

    ref, got = _both(build)

    assert (key in got.nodes()) is (key in ref.nodes()) is True
    assert got.nodes[key] == ref.nodes[key]
    assert got.nodes.get(key) == ref.nodes.get(key)
    assert got.nodes.get("absent-key", "dflt") == ref.nodes.get("absent-key", "dflt")
    assert ((key, "hub") in got.edges()) is ((key, "hub") in ref.edges()) is True
    assert got.edges[key, "hub"] == ref.edges[key, "hub"] == {"weight": 9}
    assert got.degree[key] == ref.degree[key] == 1
    assert got["hub"][key] == ref["hub"][key] == {"weight": 9}
    assert (key in got["hub"]) is (key in ref["hub"]) is True


def test_wide_int_keys_stay_distinct():
    """Ints wider than i64 take the owned exact-decimal build, not the buffer."""
    big = 2**63 + 7

    def build(g):
        g.add_edge(big, big + 1)
        return g

    ref, got = _both(build)
    assert got.number_of_nodes() == ref.number_of_nodes() == 2
    assert sorted(map(str, got.nodes())) == sorted(map(str, ref.nodes()))
    assert (big in got.nodes()) is (big + 1 in got.nodes()) is True
    assert got.degree[big] == ref.degree[big] == 1


# ---------------------------------------------------------------------------
# Error parity: the probes must still raise nx's exception with nx's payload.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["nope", 404, (9, 9), "y" * 300])
def test_missing_key_errors_match_networkx(missing):
    def build(g):
        g.add_edge("a", "b")
        return g

    ref, got = _both(build)

    for graph in (ref, got):
        with pytest.raises(KeyError) as caught:
            graph.nodes[missing]
        assert caught.value.args[0] == missing

    with pytest.raises(Exception) as ref_err:
        ref.degree[missing]
    with pytest.raises(Exception) as got_err:
        got.degree[missing]
    assert type(got_err.value).__name__ == type(ref_err.value).__name__

    for graph in (ref, got):
        with pytest.raises(KeyError):
            graph["a"][missing]
        with pytest.raises(KeyError):
            graph.edges["a", missing]


def test_unhashable_key_raises_typeerror_like_networkx():
    def build(g):
        g.add_edge("a", "b")
        return g

    ref, got = _both(build)
    for graph in (ref, got):
        with pytest.raises(TypeError):
            [] in graph.nodes()


# ---------------------------------------------------------------------------
# Identity + liveness: the borrowed probe must not have copied anything.
# ---------------------------------------------------------------------------


def test_subscript_still_returns_the_live_shared_edge_dict():
    g = fnx.Graph()
    g.add_edge("a", "b", weight=1)

    row = g["a"]["b"]
    assert row is g.edges["a", "b"], "G[u][v] must be the SAME dict as G.edges[u, v]"

    row["weight"] = 42
    row["added"] = "yes"
    assert g["a"]["b"] == {"weight": 42, "added": "yes"}
    assert g.edges["a", "b"] == {"weight": 42, "added": "yes"}
    assert g.adj["a"]["b"] == {"weight": 42, "added": "yes"}


def test_write_through_subscript_reaches_native_kernels():
    """`mark_edges_dirty` must still fire, or a later native read goes stale."""
    ref, got = _both(lambda g: (g.add_edge("a", "b", weight=1), g)[1])

    for graph in (ref, got):
        graph["a"]["b"]["weight"] = 5.0

    assert got.size(weight="weight") == ref.size(weight="weight") == 5.0
    assert dict(got.degree(weight="weight")) == dict(ref.degree(weight="weight"))


def test_probes_stay_live_across_mutation():
    ref, got = _both(lambda g: (g.add_edge("a", "b"), g)[1])

    for graph in (ref, got):
        graph.add_edge("b", "c")
    assert ("b", "c") in got.edges()
    assert got.degree["b"] == ref.degree["b"] == 2
    assert ("c" in got["b"]) is ("c" in ref["b"]) is True

    for graph in (ref, got):
        graph.remove_edge("b", "c")
    assert (("b", "c") in got.edges()) is (("b", "c") in ref.edges()) is False
    assert got.degree["b"] == ref.degree["b"] == 1
    assert ("c" in got["b"]) is ("c" in ref["b"]) is False


@pytest.mark.parametrize("cls", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_all_four_graph_classes_agree_with_networkx(cls):
    left, right = _pair(KEY_OVER_BUFFER)

    def build(mod):
        g = getattr(mod, cls)()
        g.add_edge(left, "hub", weight=1)
        g.add_edge(right, "hub", weight=2)
        g.add_edge(7, "hub", weight=3)
        return g

    ref, got = build(nx), build(fnx)

    assert sorted(map(repr, got.nodes())) == sorted(map(repr, ref.nodes()))
    for key in (left, right, 7, "hub"):
        assert (key in got.nodes()) is (key in ref.nodes()) is True
        assert got.degree[key] == ref.degree[key]
        assert got.nodes[key] == ref.nodes[key]
    assert (("nope", "hub") in got.edges()) is (("nope", "hub") in ref.edges()) is False
