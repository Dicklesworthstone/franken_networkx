"""Regression lock for br-r37-c1-lvlu7 — node keys that lie about hashing.

networkx reaches every node key through a dict, so `__hash__` decides what
happens. fnx canonicalises a key by reading its BYTES (`"str:{len}:{s}"`) and
never calls `__hash__`, so a `str` subclass with `__hash__ = None` sailed
straight past: `(Unhash("n0"), "n1") in G.edges` answered True where networkx
raises, and `Unhash("n0") in G` answered True where networkx answers False.

THE TWO PROBES WANT DIFFERENT ANSWERS, which is why this is not one fix applied
twice:

* `EdgeView.__contains__` must RAISE. nx is `v in self._adjdict[u]` inside
  `except (KeyError, ValueError)`, and TypeError is not in that tuple.
* `Graph.__contains__` and `has_node` must answer FALSE. nx is
  `try: n in self._node except TypeError: return False`.

AND THE ORDER IS PART OF THE CONTRACT. nx hashes `u`, and an absent `u`
short-circuits through KeyError WITHOUT `v` ever being hashed — so
`("missing", Unhash("n1")) in G.edges` is False, not a TypeError. A "hash both
endpoints up front" fix trades one divergence for another; `has_edge` was doing
exactly that and answering TypeError for a pair networkx calls False. Both
directions are asserted below.

Every expectation here is taken from LIVE networkx in the same test run rather
than from a recorded constant, because the recorded constants are what was
wrong.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class Unhash(str):
    """A `str` subclass that cannot be hashed. `dict[key]` raises TypeError."""

    __hash__ = None


class PlainSub(str):
    """A `str` subclass with default hashing — must behave exactly like `str`."""


def _pair(cls_name):
    reference, subject = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (reference, subject):
        graph.add_edge("n0", "n1")
    return reference, subject


def _outcome(fn):
    """The observable result: the value, or the exception type and message."""
    try:
        return ("value", fn())
    except BaseException as exc:  # noqa: BLE001 — the exception IS the contract
        return ("raise", type(exc).__name__, str(exc))


def _probes(graph):
    """Every combination the bead's acceptance names, as (label, callable)."""
    unhashable_u, unhashable_v = Unhash("n0"), Unhash("n1")
    plain_u, plain_v = PlainSub("n0"), PlainSub("n1")
    return {
        # unhashable in u position, v position, present and absent partners
        "edges: (unhash_u, present_v)": lambda: (unhashable_u, "n1") in graph.edges,
        "edges: (present_u, unhash_v)": lambda: ("n0", unhashable_v) in graph.edges,
        "edges: (unhash_u, absent_v)": lambda: (unhashable_u, "missing") in graph.edges,
        "edges: (absent_u, unhash_v)": lambda: ("missing", unhashable_v) in graph.edges,
        "edges: (unhash_u, unhash_v)": lambda: (unhashable_u, unhashable_v) in graph.edges,
        # the same shapes through has_edge, which the multigraph views delegate to
        "has_edge(unhash_u, present_v)": lambda: graph.has_edge(unhashable_u, "n1"),
        "has_edge(present_u, unhash_v)": lambda: graph.has_edge("n0", unhashable_v),
        "has_edge(absent_u, unhash_v)": lambda: graph.has_edge("missing", unhashable_v),
        "has_edge(unhash_u, absent_v)": lambda: graph.has_edge(unhashable_u, "missing"),
        # node membership, both spellings
        "unhash in G": lambda: unhashable_u in graph,
        "has_node(unhash)": lambda: graph.has_node(unhashable_u),
        "unhash in G.nodes": lambda: unhashable_u in graph.nodes,
        # a PLAIN subclass must be indistinguishable from str
        "edges: (plain_u, present_v)": lambda: (plain_u, "n1") in graph.edges,
        "edges: (present_u, plain_v)": lambda: ("n0", plain_v) in graph.edges,
        "edges: (plain_u, absent_v)": lambda: (plain_u, "missing") in graph.edges,
        "has_edge(plain_u, plain_v)": lambda: graph.has_edge(plain_u, plain_v),
        "plain in G": lambda: plain_u in graph,
        "has_node(plain)": lambda: graph.has_node(plain_u),
        # exact str, the control: none of this may disturb the ordinary path
        "edges: (str, str) present": lambda: ("n0", "n1") in graph.edges,
        "edges: (str, str) absent": lambda: ("n0", "missing") in graph.edges,
        "str in G": lambda: "n0" in graph,
        "has_edge(str, str)": lambda: graph.has_edge("n0", "n1"),
    }


PROBE_LABELS = list(_probes(nx.Graph()))


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
@pytest.mark.parametrize("label", PROBE_LABELS)
def test_matches_live_networkx(cls_name, label):
    """Value for value, exception type for exception type, message for message."""
    reference, subject = _pair(cls_name)
    expected = _outcome(_probes(reference)[label])
    observed = _outcome(_probes(subject)[label])
    assert observed == expected


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_an_absent_source_never_hashes_the_target(cls_name):
    """THE ORDER TEST. `u` is hashed first; an absent `u` short-circuits.

    An implementation that hashes both endpoints up front passes every other
    test in this file and fails this one — which is what `has_edge` did: it
    raised TypeError for a pair networkx answers False.
    """
    reference, subject = _pair(cls_name)
    assert (("missing", Unhash("n1")) in reference.edges) is False
    assert (("missing", Unhash("n1")) in subject.edges) is False, (
        f"{cls_name}: hashed the target before resolving an absent source"
    )
    assert subject.has_edge("missing", Unhash("n1")) is False


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_an_unhashable_endpoint_raises_from_the_edge_view(cls_name):
    """The edge view RAISES where node membership answers False.

    Both are TypeError from a dict in networkx; only one of them is caught.
    """
    reference, subject = _pair(cls_name)
    with pytest.raises(TypeError) as reference_err:
        (Unhash("n0"), "n1") in reference.edges  # noqa: B015 — membership is the call
    with pytest.raises(TypeError) as subject_err:
        (Unhash("n0"), "n1") in subject.edges  # noqa: B015
    assert str(subject_err.value) == str(reference_err.value)


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_an_unhashable_node_is_absent_not_an_error(cls_name):
    reference, subject = _pair(cls_name)
    assert (Unhash("n0") in reference) is False
    assert (Unhash("n0") in subject) is False
    assert reference.has_node(Unhash("n0")) is False
    assert subject.has_node(Unhash("n0")) is False


@pytest.mark.parametrize("cls_name", CLASS_NAMES)
def test_ordinary_keys_are_undisturbed(cls_name):
    """The guard must not cost the exact-`str` and int paths their behaviour."""
    reference, subject = _pair(cls_name)
    for graph in (reference, subject):
        graph.add_edge(7, 8)
    for probe in (("n0", "n1"), ("n1", "n0"), ("n0", "absent"), (7, 8), (8, 7)):
        assert (probe in subject.edges) == (probe in reference.edges), probe
    for key in ("n0", "absent", 7, 7.0, True, None):
        assert (key in subject) == (key in reference), key
        assert subject.has_node(key) == reference.has_node(key), key
