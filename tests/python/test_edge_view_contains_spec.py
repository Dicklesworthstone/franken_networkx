"""`<spec> in G.edges` accepts far more than a `(u, v)` tuple — pin all of it.

br-r37-c1-dtrpe moved networkx's permissive `EdgeView.__contains__` semantics
out of a Python wrapper in `franken_networkx/__init__.py` and into the Rust
slot, so that `x in G.edges` reaches the C slot directly. The wrapper WAS the
specification, and deleting it is a parity change before it is a perf change:
every shape below is a behaviour the wrapper produced, and each one is asserted
against live networkx rather than against a recorded expectation.

networkx's undirected `EdgeView.__contains__` (3.6.1)::

    try:
        u, v = e[:2]
        return v in self._adjdict[u] or u in self._adjdict[v]
    except (KeyError, ValueError):
        return False

so the outcome for a non-tuple spec is decided by WHICH exception `e[:2]` and
the unpack raise, and only KeyError and ValueError become False. Getting that
wrong is silent: `"x" in G.edges` is a common always-False drop-in guard, and a
TypeError there crashes callers that networkx never crashes.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


class _Unhashable(list):
    """A list subclass, so it is a plausible node key and cannot be hashed."""


def _outcome(view, spec):
    """Return the observable result: the boolean, or the exception + message."""
    try:
        return ("value", spec in view)
    except BaseException as exc:  # noqa: BLE001 — the exception IS the contract
        return ("raise", type(exc).__name__, str(exc))


# Every spec shape the wrapper handled, plus the ones it got wrong. `id` is what
# a failure reports, so keep them descriptive.
SPECS = [
    ("present-tuple", lambda: ("a", "b")),
    ("reversed-tuple", lambda: ("b", "a")),
    ("absent-tuple", lambda: ("a", "zz")),
    ("three-tuple-present", lambda: ("a", "b", {"w": 1})),
    ("three-tuple-absent", lambda: ("a", "zz", {"w": 1})),
    ("one-tuple", lambda: ("a",)),
    ("empty-tuple", lambda: ()),
    ("present-list", lambda: ["a", "b"]),
    ("one-list", lambda: ["a"]),
    ("three-list", lambda: ["a", "b", "c"]),
    ("str-len2", lambda: "ab"),
    ("str-len1", lambda: "a"),
    ("str-empty", lambda: ""),
    ("str-len3", lambda: "abc"),
    ("int", lambda: 5),
    ("none", lambda: None),
    ("float", lambda: 1.5),
    ("bool", lambda: True),
    ("set", lambda: {"a", "b"}),
    ("dict", lambda: {"a": 1, "b": 2}),
    ("generator", lambda: (c for c in ("a", "b"))),
    ("bytes", lambda: b"ab"),
    ("range", lambda: range(2)),
    ("int-pair", lambda: (1, 2)),
    ("none-endpoint", lambda: ("a", None)),
    ("nested-tuple-endpoint", lambda: (("a", "b"), "b")),
]


def _graphs():
    reference, subject = nx.Graph(), fnx.Graph()
    for graph in (reference, subject):
        graph.add_edge("a", "b", weight=1)
        graph.add_edge("b", "c", weight=2)
    return reference, subject


@pytest.mark.parametrize("label,make_spec", SPECS, ids=[s[0] for s in SPECS])
def test_edge_spec_outcome_matches_networkx(label, make_spec):
    reference, subject = _graphs()
    assert _outcome(subject.edges, make_spec()) == _outcome(reference.edges, make_spec())


def test_the_always_false_drop_in_guard_does_not_raise():
    """The shape that motivated the wrapper (br-r37-c1-edgeviewcontains)."""
    _reference, subject = _graphs()
    assert ("x" in subject.edges) is False
    assert ("zz" in subject.edges) is False


def test_dict_spec_is_a_missing_key_not_a_type_error():
    """Slices are hashable since 3.12, so `{...}[:2]` is a KeyError -> False.

    The Python wrapper only caught TypeError around `e[:2]` and let this
    KeyError escape, which is why fnx raised where networkx returned False.
    """
    reference, subject = _graphs()
    assert ({"a": 1, "b": 2} in subject.edges) is False
    assert ({"a": 1, "b": 2} in reference.edges) is False


def test_non_subscriptable_specs_keep_networkx_wording():
    """A TypeError here must be CPython's own, not a message we invented."""
    reference, subject = _graphs()
    for spec in (5, None, 1.5, True, {"a", "b"}):
        with pytest.raises(TypeError) as subject_err:
            spec in subject.edges  # noqa: B015 — membership is the call
        with pytest.raises(TypeError) as reference_err:
            spec in reference.edges  # noqa: B015
        assert str(subject_err.value) == str(reference_err.value)
        assert "is not subscriptable" in str(subject_err.value)


def test_longer_specs_use_the_first_two_endpoints():
    _reference, subject = _graphs()
    assert (("a", "b", "ignored", "also ignored") in subject.edges) is True
    assert (("a", "zz", "ignored") in subject.edges) is False


def test_str_spec_indexes_characters_not_the_whole_string():
    """`"ab"[:2]` unpacks to two ONE-CHARACTER endpoints, which happen to exist."""
    reference, subject = _graphs()
    assert ("ab" in subject.edges) is ("ab" in reference.edges) is True
    assert ("ac" in subject.edges) is ("ac" in reference.edges) is False


def test_unhashable_endpoint_raises_exactly_as_networkx_does():
    """FIXED in br-r37-c1-lvlu7; this test moved, as its previous form said it would.

    It used to pin the divergence — networkx raising from `adj[u]` while fnx
    canonicalised the characters and answered False — and to say that whoever
    changed the layer below `__contains__` would see it move. That happened:
    the membership paths now assert networkx's hashability contract, so both
    libraries raise the same TypeError with the same message. The full
    order-sensitive matrix lives in `test_unhashable_key_parity.py`.
    """
    reference, subject = _graphs()
    with pytest.raises(TypeError, match="unhashable type") as subject_err:
        (_Unhashable(["a"]), "b") in subject.edges  # noqa: B015
    with pytest.raises(TypeError, match="unhashable type") as reference_err:
        (_Unhashable(["a"]), "b") in reference.edges  # noqa: B015
    assert str(subject_err.value) == str(reference_err.value)


# --------------------------------------------------------------------------
# Multigraphs: the same question, a different contract (br-r37-c1-6fs77).
#
# networkx's MultiEdgeView takes `len(e)`, unpacks 2 or 3 elements, raises
# ValueError for any other length — and for a 2-element spec defaults the KEY
# TO ZERO. It does not mean "any key". fnx reported True as soon as the pair
# existed, so every multigraph whose keys are not 0 answered membership wrongly,
# in the direction of claiming edges that are not there.
# --------------------------------------------------------------------------
MULTI_CLASSES = ["MultiGraph", "MultiDiGraph"]

MULTI_SPECS = [
    ("pair-with-nonzero-key", lambda: ("a", "b")),
    ("triple-with-that-key", lambda: ("a", "b", "x")),
    ("triple-with-key-zero", lambda: ("a", "b", 0)),
    ("pair-with-auto-key", lambda: ("c", "d")),
    ("triple-auto-key-zero", lambda: ("c", "d", 0)),
    ("triple-absent-key", lambda: ("c", "d", 1)),
    ("pair-of-parallel-edges", lambda: ("e", "f")),
    ("triple-second-parallel", lambda: ("e", "f", 1)),
    ("reversed-pair", lambda: ("b", "a")),
    ("reversed-triple", lambda: ("b", "a", "x")),
    ("three-list", lambda: ["a", "b", "x"]),
    ("absent-pair", lambda: ("zz", "yy")),
    ("four-tuple", lambda: ("a", "b", "x", "extra")),
    ("one-tuple", lambda: ("a",)),
    ("str-len2", lambda: "ab"),
    ("int", lambda: 5),
    ("bool-key", lambda: ("c", "d", False)),
]


def _multi_graphs(cls_name):
    reference, subject = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (reference, subject):
        graph.add_edge("a", "b", key="x")
        graph.add_edge("c", "d")
        graph.add_edge("e", "f", key=0)
        graph.add_edge("e", "f", key=1)
    return reference, subject


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
@pytest.mark.parametrize("label,make_spec", MULTI_SPECS, ids=[s[0] for s in MULTI_SPECS])
def test_multi_edge_spec_outcome_matches_networkx(cls_name, label, make_spec):
    reference, subject = _multi_graphs(cls_name)
    assert _outcome(subject.edges, make_spec()) == _outcome(reference.edges, make_spec())


@pytest.mark.parametrize("cls_name", MULTI_CLASSES)
def test_a_two_element_multi_spec_means_key_zero_not_any_key(cls_name):
    """The regression itself, stated on its own so a failure names it.

    An implementation that answers "does the pair exist" passes every other
    test in this file and fails this one.
    """
    reference, subject = _multi_graphs(cls_name)
    assert (("a", "b") in reference.edges) is False
    assert (("a", "b") in subject.edges) is False, (
        f"{cls_name}: a 2-element spec matched an edge whose only key is 'x'; "
        "networkx probes key 0"
    )
    # And key 0 present still answers True, so the fix is not just "always False".
    assert (("c", "d") in subject.edges) is (("c", "d") in reference.edges) is True


def test_the_rust_slot_is_reached_directly():
    """The lever IS the missing Python frame; a rebind would undo it silently."""
    from franken_networkx import _fnx

    _reference, subject = _graphs()
    assert type(subject.edges) is _fnx.EdgeView
    contains = _fnx.EdgeView.__contains__
    assert type(contains).__name__ == "wrapper_descriptor", contains
    assert getattr(contains, "__closure__", None) is None
