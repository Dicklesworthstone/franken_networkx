"""Edge lookup must be key-type and key-LENGTH exact against networkx.

br-r37-c1-tjp0g. This is the gate for a pending change to
`PyDiGraph::get_edge_data`: replacing its two `node_key_to_string` allocations
with nested `with_node_key_str`, which BORROWS the canonical key instead of
allocating it. That function backs `DiGraph.edges[u, v]`, `G.get_edge_data(u, v)`
and `G[u][v]`, so a canonicalization regression there is silent and broad.

Why key LENGTH is the discriminating axis, not just key type:
`with_node_key_str` writes `"str:{len}:{s}"` into a fixed 128-byte
(`CANONICAL_KEY_STACK_BUF`) buffer and takes an OWNED `format!` fallback when the
key does not fit. So a string node has two distinct code paths with a boundary at
roughly 120 characters, and a borrow lever that is correct on short keys can be
wrong on long ones — or vice versa. Every case here is therefore run at several
lengths straddling that boundary.

These assertions hold on HEAD today; they exist so the change cannot alter
behaviour unnoticed. Written before the lever, because the lever needs a build
and the disk brake currently forbids one.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]

# Straddle the 128-byte canonical buffer: "str:{len}:{s}" is len(s) + ~8 bytes,
# so the owned-fallback branch begins a little under 120 characters.
KEY_LENGTHS = [1, 7, 63, 110, 118, 119, 120, 121, 130, 260, 1000]


def _pair(class_name):
    return getattr(fnx, class_name)(), getattr(nx, class_name)()


def _outcome(callable_):
    try:
        return ("ok", repr(callable_()))
    except Exception as exc:  # noqa: BLE001 - the exception is part of the contract
        return (type(exc).__name__, repr(exc.args))


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_present_edge_lookup_matches_across_the_canonical_buffer_boundary(
    class_name, length
):
    """A PRESENT edge, at key lengths either side of the 128-byte buffer."""
    u = "u" * length
    v = "v" * length
    results = {}
    for module, graph in zip((fnx, nx), _pair(class_name)):
        graph.add_edge(u, v, weight=3)
        results[module.__name__] = (
            _outcome(lambda g=graph: g.edges[u, v]),
            _outcome(lambda g=graph: g.get_edge_data(u, v)),
            _outcome(lambda g=graph: g[u][v]),
        )
    assert results["franken_networkx"] == results["networkx"], (
        f"{class_name}, key length {length}: lookup diverged. This length "
        f"straddles the canonical-key stack buffer, where the borrowed and "
        f"owned canonicalization branches differ."
    )


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_absent_edge_lookup_matches_across_the_boundary(class_name, length):
    """An ABSENT edge takes a different branch — it never reaches materialization."""
    u = "u" * length
    v = "v" * length
    missing = "z" * length
    results = {}
    for module, graph in zip((fnx, nx), _pair(class_name)):
        graph.add_edge(u, v, weight=3)
        graph.add_node(missing)
        results[module.__name__] = (
            _outcome(lambda g=graph: g.edges[u, missing]),
            _outcome(lambda g=graph: g.get_edge_data(u, missing)),
            _outcome(lambda g=graph: g.get_edge_data(u, missing, default="D")),
            _outcome(lambda g=graph: g.has_edge(u, missing)),
        )
    assert results["franken_networkx"] == results["networkx"], (
        f"{class_name}, key length {length}: absent-edge lookup diverged"
    )


NON_STRING_KEYS = [
    (1, 2),
    (0, 1),
    (-3, 7),
    (1.5, 2.5),
    (True, False),
    ((1, 2), (3, 4)),
    ("1", 1),
    (frozenset({1}), frozenset({2})),
    (None, "x"),
]


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("u,v", NON_STRING_KEYS)
def test_non_string_endpoint_lookup_matches(class_name, u, v):
    """Non-str keys take the OWNED canonicalization branch in either design.

    The borrow lever only short-circuits exact `str`, so these are the control:
    they must be completely unaffected by it. `("1", 1)` is deliberately
    included — a str and an int that must NOT collide.
    """
    results = {}
    for module, graph in zip((fnx, nx), _pair(class_name)):
        # The insertion is compared too: some keys are REJECTED (networkx
        # refuses `None` as a node), and the rejection is part of the contract
        # just as much as the lookup that would follow it.
        results[module.__name__] = (
            _outcome(lambda g=graph: g.add_edge(u, v, weight=3)),
            _outcome(lambda g=graph: g.edges[u, v]),
            _outcome(lambda g=graph: g.get_edge_data(u, v)),
            _outcome(lambda g=graph: g.get_edge_data(v, u)),
        )
    assert results["franken_networkx"] == results["networkx"], (
        f"{class_name}: lookup with endpoints {u!r}, {v!r} diverged"
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_unicode_and_empty_keys_match(class_name):
    """Multi-byte characters make len(str) and len(utf-8) disagree.

    The canonical form embeds a length; if it ever embeds the BYTE length where
    Python counts characters, these collide or miss. The empty string is the
    other end of the same axis.
    """
    cases = ["", "é", "é" * 60, "日本語", "日本語" * 40, "a\x00b", "🜲🜲🜲"]
    results = {}
    for module, graph in zip((fnx, nx), _pair(class_name)):
        for i, key in enumerate(cases):
            graph.add_edge(key, f"target{i}", weight=i)
        results[module.__name__] = [
            (
                _outcome(lambda g=graph, k=key, i=i: g.edges[k, f"target{i}"]),
                _outcome(lambda g=graph, k=key, i=i: g.get_edge_data(k, f"target{i}")),
            )
            for i, key in enumerate(cases)
        ]
    assert results["franken_networkx"] == results["networkx"], (
        f"{class_name}: unicode/empty key lookup diverged"
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_keys_differing_only_after_the_buffer_boundary_do_not_collide(class_name):
    """The sharpest case for a borrowed fixed-size buffer.

    Two keys sharing a long common prefix and differing only past the 128-byte
    canonical buffer. An implementation that truncates into the buffer — instead
    of falling back to the owned form — reports these as the SAME edge. That is
    a silent wrong-answer bug no length-agnostic test can catch.
    """
    prefix = "p" * 200
    u1, u2 = prefix + "AAA", prefix + "BBB"
    results = {}
    for module, graph in zip((fnx, nx), _pair(class_name)):
        graph.add_edge(u1, "t", weight=1)
        graph.add_edge(u2, "t", weight=2)
        results[module.__name__] = (
            graph.number_of_edges(),
            _outcome(lambda g=graph: g.edges[u1, "t"]),
            _outcome(lambda g=graph: g.edges[u2, "t"]),
            _outcome(lambda g=graph: g.get_edge_data(u1, "t")),
            _outcome(lambda g=graph: g.get_edge_data(u2, "t")),
        )
    assert results["franken_networkx"] == results["networkx"], (
        f"{class_name}: two keys differing only past the canonical buffer "
        f"boundary were confused"
    )
    assert results["franken_networkx"][0] == 2, "both edges must exist separately"


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("length", [7, 119, 121, 300])
def test_lookup_is_repeatable_and_returns_the_live_dict(class_name, length):
    """A borrowed key must not leave the returned dict tied to a dead buffer.

    Reads the same edge twice and mutates through the first result. If the
    lookup ever returned a dict backed by the scratch buffer rather than the
    graph's own storage, the second read would not see the write.
    """
    u, v = "u" * length, "v" * length
    for module, graph in zip((fnx, nx), _pair(class_name)):
        graph.add_edge(u, v, weight=1)
        first = graph.edges[u, v]
        first["marker"] = 99
        assert graph.edges[u, v].get("marker") == 99, (
            f"{module.__name__} {class_name} length {length}: write through the "
            f"returned dict was not visible on re-read"
        )
        assert graph.get_edge_data(u, v).get("marker") == 99
