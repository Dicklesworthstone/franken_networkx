"""Regression lock for br-r37-c1-padm6 — the native ``__contains__`` private-node
override probe.

``n in G`` is the one node-membership spelling that cannot escape a Python-level
private-storage probe. fnx's escape hatch for the other spellings is a per-INSTANCE
method shadow: ``has_node`` is bound straight to the raw native slot, and only a graph
that actually gains NetworkX private storage gets a shadowing bound method installed in
its instance ``__dict__``. A dunder is looked up on the TYPE, never the instance, so
``Graph.__contains__`` has to stay one type-level function — which meant every ordinary
graph paid a Python frame plus an instance-dict probe on every membership test
(measured 2026-08-04: nx 63.4 ns, fnx ``n in G`` 236.8 ns vs fnx ``G.has_node(n)``
98.5 ns on identical native lookup code).

The probe now lives in native ``__contains__`` behind a Rust bool that is set only by
``_set_private_override`` — the single install funnel reached by the four ``_node``
property setters. With the flag clear the native ``__contains__`` is exactly
``has_node``; with it set, the assigned mapping answers.

The load-bearing negative case is
``test_assigned_private_node_mapping_answers_membership``: with the flag stuck false
(a native probe that is never armed) the NATIVE store answers instead of the assigned
mapping, so every one of its assertions inverts. That state is reachable — writing the
override key straight into ``__dict__`` bypasses the funnel — and
``test_probe_is_gated_on_the_flag_not_merely_on_the_dict_key`` pins it.
"""

from __future__ import annotations

import copy
import pickle
import types

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]

# Mixed key kinds: str, int, float, bool and None all reach different branches of the
# canonicalization path, and a list is the unhashable case nx answers False for.
PRESENT_KEYS = ["a", 7, 2.5]
PROBE_KEYS = ["a", "absent", 7, 2.5, True, None]

PRIVATE_OVERRIDE_KEY = "_fnx_private_node_override"


def _pair(name):
    """A live networkx graph and the fnx graph of the same class, same contents."""
    gnx = getattr(nx, name)()
    gfnx = getattr(fnx, name)()
    for graph in (gnx, gfnx):
        graph.add_nodes_from(PRESENT_KEYS)
    return gnx, gfnx


def _round_trip(graph):
    return pickle.loads(  # nosec B301  # ubs:ignore - trusted round trip
        pickle.dumps(graph)
    )


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_contains_is_a_native_slot_not_a_python_wrapper(name):
    """The lever itself: no Python-level ``__contains__`` wrapper on any class.

    Reinstalling one would silently restore the ~138 ns per-membership-test tax on
    every ordinary graph, so this is the structural guard for the perf claim.
    """
    slot = getattr(fnx, name).__dict__.get("__contains__")
    assert slot is not None, f"{name} does not define __contains__"
    assert not isinstance(slot, types.FunctionType), (
        f"{name}.__contains__ is a Python function ({slot!r}); the private-override "
        "probe belongs in native __contains__ behind the Rust flag"
    )


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_ordinary_graph_membership_matches_has_node_and_networkx(name):
    """With no private storage, ``n in G`` must equal ``G.has_node(n)`` and nx."""
    gnx, gfnx = _pair(name)
    for key in PROBE_KEYS:
        expected = key in gnx
        assert (key in gfnx) == expected, f"{name}: {key!r} membership diverges from nx"
        assert gfnx.has_node(key) == expected, (
            f"{name}: {key!r} has_node disagrees with __contains__"
        )
        assert (key in gfnx.nodes) == expected, (
            f"{name}: {key!r} nodes-view membership disagrees"
        )
    # The native slot answers with a real bool, not merely something truthy.
    assert isinstance(gfnx.has_node("a"), bool)
    assert isinstance("a" in gfnx, bool)


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_unhashable_key_membership_is_false_not_an_error(name):
    """nx returns False for an unhashable key rather than raising TypeError."""
    gnx, gfnx = _pair(name)
    unhashable = ["not", "hashable"]
    assert unhashable not in gnx
    assert unhashable not in gfnx
    assert not gfnx.has_node(unhashable)
    assert {"also": "unhashable"} not in gfnx


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_assigned_private_node_mapping_answers_membership(name):
    """NEGATIVE CASE — a flag that is never armed fails every assertion here.

    After ``G._node = <mapping>`` the assigned mapping is the authority: its keys are
    present and the graph's own native nodes are gone. An unarmed native probe would
    answer from the native store and invert all four results.
    """
    gnx, gfnx = _pair(name)
    for graph in (gnx, gfnx):
        graph._node = {"private": {}, "other": {"tag": 1}}

    for key in ("private", "other"):
        assert key in gnx
        assert key in gfnx, (
            f"{name}: assigned mapping key {key!r} not seen by __contains__ — the "
            "native private-override flag was not armed"
        )
    for key in PRESENT_KEYS:
        assert key not in gnx
        assert key not in gfnx, (
            f"{name}: native node {key!r} still reported present after _node was "
            "assigned — __contains__ consulted the native store, not the mapping"
        )
    # The wrapper it replaced also suppressed TypeError from the mapping probe.
    assert ["unhashable"] not in gnx
    assert ["unhashable"] not in gfnx


@pytest.mark.parametrize("name", CLASS_NAMES)
@pytest.mark.parametrize("dunder", ["__len__", "__iter__"])
def test_len_and_iter_are_native_slots_not_python_wrappers(name, dunder):
    """br-r37-c1-l7ww9: the same lever, for the other two node dunders.

    ``len(G)`` measured 0.4074x against networkx purely because of the Python
    wrapper here — networkx's own ``__len__`` is a Python method returning
    ``len(self._node)``, so this was a frame-versus-two-frames loss. Removing it
    took the row to 2.0225x. Reinstalling a wrapper would give the whole thing
    back silently, hence this structural guard.
    """
    slot = getattr(fnx, name).__dict__.get(dunder)
    assert slot is not None, f"{name} does not define {dunder}"
    assert not isinstance(slot, types.FunctionType), (
        f"{name}.{dunder} is a Python function ({slot!r}); the private-override "
        f"probe belongs in the native {dunder} behind the Rust flag"
    )


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_ordinary_graph_len_and_iter_match_networkx(name):
    gnx, gfnx = _pair(name)
    assert len(gfnx) == len(gnx)
    assert list(gfnx) == list(gnx)
    assert gfnx.number_of_nodes() == len(gfnx)


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_assigned_private_node_mapping_answers_len_and_iter(name):
    """NEGATIVE CASE — an unarmed native probe fails every assertion here.

    After ``G._node = <mapping>`` the graph's length and iteration order come
    from the mapping, not from the native store, and neither has anything to do
    with how many nodes were added. A probe that read the native store would
    report 3 and the original keys.
    """
    gnx, gfnx = _pair(name)
    mapping = {"private": {}, "other": {"tag": 1}}
    for graph in (gnx, gfnx):
        graph._node = dict(mapping)

    assert len(gnx) == 2
    assert len(gfnx) == 2, (
        f"{name}: len() answered from the native store after _node was assigned"
    )
    assert list(gfnx) == list(gnx) == ["private", "other"], (
        f"{name}: iteration answered from the native store, or in the wrong order"
    )
    # Length tracks the mapping as it changes, with no node added to the graph.
    for graph in (gnx, gfnx):
        graph._node["third"] = {}
    assert len(gfnx) == len(gnx) == 3
    assert list(gfnx) == list(gnx)


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_iterating_private_storage_raises_like_networkx_when_it_changes_size(name):
    """Iterating the mapping ITSELF, not a copy, is part of the contract."""
    gnx, gfnx = _pair(name)
    for graph in (gnx, gfnx):
        graph._node = {"private": {}, "other": {}}

    def mutate_during_iteration(graph):
        with pytest.raises(RuntimeError) as err:
            for _ in graph:
                graph._node["grown"] = {}
        return str(err.value)

    assert mutate_during_iteration(gfnx) == mutate_during_iteration(gnx)


def test_len_and_iter_are_gated_on_the_flag_not_merely_on_the_dict_key():
    """Sibling of the membership gate test, for the two new probes."""
    bypassed = fnx.Graph()
    bypassed.add_nodes_from(PRESENT_KEYS)
    bypassed.__dict__[PRIVATE_OVERRIDE_KEY] = {"private": {}}
    assert len(bypassed) == len(PRESENT_KEYS)
    assert list(bypassed) == PRESENT_KEYS

    through_funnel = fnx.Graph()
    through_funnel.add_nodes_from(PRESENT_KEYS)
    through_funnel._node = {"private": {}}
    assert len(through_funnel) == 1
    assert list(through_funnel) == ["private"]


def test_probe_is_gated_on_the_flag_not_merely_on_the_dict_key():
    """The Rust flag — not the presence of the dict key — is what arms the probe.

    Writing the override key straight into ``__dict__`` bypasses
    ``_set_private_override``, the single install funnel, so the flag stays clear and
    the native store must keep answering. If the native probe read the instance dict
    unconditionally this would report the mapping's node, and the ordinary-graph fast
    path this lever exists to create would not exist.
    """
    bypassed = fnx.Graph()
    bypassed.add_nodes_from(PRESENT_KEYS)
    bypassed.__dict__[PRIVATE_OVERRIDE_KEY] = {"private": {}}
    assert "private" not in bypassed
    assert "a" in bypassed

    through_funnel = fnx.Graph()
    through_funnel.add_nodes_from(PRESENT_KEYS)
    through_funnel._node = {"private": {}}
    assert "private" in through_funnel
    assert "a" not in through_funnel


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_private_override_survives_reassignment_and_further_mutation(name):
    """The flag is sticky, and the mapping stays authoritative when it changes.

    The flag only *enables* the instance-dict lookup — the mapping itself is the
    authority — so replacing the mapping must be visible immediately.
    """
    gnx, gfnx = _pair(name)
    for graph in (gnx, gfnx):
        graph._node = {"first": {}}
    assert "first" in gnx
    assert "first" in gfnx

    for graph in (gnx, gfnx):
        graph._node = {"second": {}}
    assert "second" in gnx
    assert "second" in gfnx
    assert "first" not in gnx
    assert "first" not in gfnx

    # A live mutation of the assigned mapping is seen without re-assignment.
    for graph in (gnx, gfnx):
        graph._node["third"] = {}
    assert "third" in gnx
    assert "third" in gfnx


@pytest.mark.parametrize("name", CLASS_NAMES)
@pytest.mark.parametrize(
    "clone",
    [
        pytest.param(copy.copy, id="copy"),
        pytest.param(copy.deepcopy, id="deepcopy"),
        pytest.param(_round_trip, id="pickle"),
    ],
)
def test_clones_of_a_private_storage_graph_stay_self_consistent(name, clone):
    """A clone must never end up with the mapping present but the flag clear.

    That desync is the one way the native probe can go wrong: ``n in H`` would answer
    from the native store while ``H.has_node(n)`` answered from the mapping shadow.
    Whatever a clone inherits, the three membership spellings must agree.

    NOTE: fnx's copy/deepcopy/pickle paths drop ``_fnx_``-prefixed instance keys, so a
    clone does NOT inherit assigned private storage the way networkx's ``__dict__``
    copy does. That divergence predates this lever (the skip lives in
    ``_graph_deepcopy`` / ``_make_reduce_ex_preserving_frozen``, both untouched by it)
    and is tracked separately as br-r37-c1-s8obc — this test deliberately asserts only
    the internal consistency that the flag owns, so it blesses neither answer.
    """
    _, gfnx = _pair(name)
    gfnx._node = {"private": {}}

    clone_graph = clone(gfnx)
    for key in ("private", *PRESENT_KEYS, "absent"):
        contains = key in clone_graph
        assert clone_graph.has_node(key) == contains, (
            f"{name}: clone disagrees on {key!r} — __contains__ says {contains}, "
            f"has_node says {clone_graph.has_node(key)} (flag/mapping desync)"
        )
        assert (key in clone_graph.nodes) == contains, (
            f"{name}: clone nodes-view disagrees on {key!r}"
        )

    # The source is unaffected by cloning.
    assert "private" in gfnx
    assert PRESENT_KEYS[0] not in gfnx


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_subgraph_of_a_private_storage_graph_stays_self_consistent(name):
    """A derived subgraph must not end up with a mapping present but the flag clear.

    Same scope note as the clone test: fnx's subgraph induction reads the assigned
    mapping where nx intersects it with the (unassigned) adjacency and yields an empty
    subgraph. That divergence is independent of this lever — ``has_node`` is the raw
    native slot with no probe in either build and it also reports the mapping's node,
    so the node is genuinely in the derived graph's native store — and is tracked as
    br-r37-c1-w4754. What the flag owns, and what is asserted here, is that the three
    membership spellings agree on whatever the subgraph does contain.
    """
    _, gfnx = _pair(name)
    gfnx._node = {"private": {}}

    sub_fnx = gfnx.subgraph(["private"])
    for key in ("private", *PRESENT_KEYS, "absent"):
        contains = key in sub_fnx
        assert sub_fnx.has_node(key) == contains, (
            f"{name}: subgraph disagrees on {key!r} — __contains__ says {contains}, "
            f"has_node says {sub_fnx.has_node(key)} (flag/mapping desync)"
        )
        assert (key in sub_fnx.nodes) == contains, (
            f"{name}: subgraph nodes-view disagrees on {key!r}"
        )


def test_private_storage_on_one_graph_does_not_arm_another():
    """The flag is per-instance: an ordinary graph keeps the native fast path.

    A flag stored anywhere shared (the class, a module global) would make every graph
    in the process pay the instance-dict probe once any graph gained private storage.
    """
    armed = fnx.Graph()
    armed.add_nodes_from(PRESENT_KEYS)
    armed._node = {"private": {}}
    assert "private" in armed

    ordinary = fnx.Graph()
    ordinary.add_nodes_from(PRESENT_KEYS)
    assert "private" not in ordinary
    for key in PRESENT_KEYS:
        assert key in ordinary
        assert ordinary.has_node(key)
