"""br-r37-c1-vaayu — the private-override helper no longer double-registers.

`_set_private_override` called `self._fnx_register_gc_dict(vars(self))` and then
`setattr(...)`, which reaches the same registration again inside every class's
`__setattr__` wrapper. Since `vars(self)` is identity-stable, the same dict was
registered twice per assignment, and a reverse view makes three such assignments
at construction.

    reverse(copy=False), balanced square, N=4000, t_nx/t_fnx:
      DiGraph        0.6243 -> 0.6494 / 0.6512 / 0.6489   (three runs)
      MultiDiGraph   0.6486 -> 0.6772

THE REMOVAL RESTS ON AN INVARIANT, and that invariant is what this file pins:
setting one of the four private overrides must still reach
`_fnx_register_gc_dict` with the instance dict. If that stops holding, the
registration silently stops happening and the failure is a GC-lifetime bug —
invisible to ordinary parity tests, and the kind of thing otherwise found by a
crash months later.

It is pinned by COUNTING the registration calls, not by reading source. A draft
that used `inspect.getsource` on `__setattr__` passed alone and failed in the
full suite because another test rebinds that wrapper — an order-dependent test
of a property that is not order-dependent.
"""

from __future__ import annotations

import gc

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
OVERRIDE_NAMES = [
    fnx._PRIVATE_NODE_OVERRIDE,
    fnx._PRIVATE_ADJ_OVERRIDE,
    fnx._PRIVATE_SUCC_OVERRIDE,
    fnx._PRIVATE_PRED_OVERRIDE,
]


@pytest.mark.parametrize("cls_name", CLASSES)
def test_setting_a_private_override_reaches_the_gc_registration(cls_name):
    """The invariant the removal depends on, checked BEHAVIOURALLY.

    An earlier draft asserted this by reading ``inspect.getsource`` of
    ``__setattr__``. That passed alone and failed in the full suite, because
    another test rebinds the wrapper — an order-dependent test of a property
    that is not order-dependent. Counting the actual registration calls during
    an override assignment is both stronger and stable.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b")
    calls = []
    original = type(graph)._fnx_register_gc_dict

    class _Counting:
        def __get__(self, obj, owner=None):
            def call(mapping):
                calls.append(mapping)
                return original.__get__(obj, owner)(mapping)
            return call

    try:
        type(graph)._fnx_register_gc_dict = _Counting()
        fnx._set_private_override(graph, fnx._PRIVATE_NODE_OVERRIDE, {"only": {}})
    finally:
        type(graph)._fnx_register_gc_dict = original
    assert calls, (
        f"{cls_name}: setting a private override no longer registers the "
        "instance dict — br-r37-c1-vaayu removed the explicit registration on "
        "the strength of the setattr wrapper still doing it"
    )
    assert all(mapping is vars(graph) for mapping in calls), (
        "the registered mapping must be the instance dict itself"
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_override_names_are_never_public_adjacency_names(cls_name):
    """The second half: the override names must not hit the early return.

    Each wrapper returns early, WITHOUT registering, for its public adjacency
    properties. That path has to be unreachable for these four names.
    """
    for name in OVERRIDE_NAMES:
        assert name.startswith("_fnx_private_"), name
        assert name not in {"adj", "succ", "pred"}, (name, cls_name)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_assigned_private_storage_still_dispatches(cls_name):
    """End-to-end: the behaviour the helper exists to enable."""
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    graph._node = {"only": {}}
    assert graph.has_node("only")
    assert not graph.has_node("a")
    assert graph.number_of_nodes() == 1
    assert graph.order() == 1


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_view_still_matches_networkx(cls_name):
    """The construction path that makes three override assignments."""
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
    rnx, rfx = gnx.reverse(copy=False), gfx.reverse(copy=False)
    assert sorted(rfx.edges()) == sorted(rnx.edges())
    assert sorted(rfx.nodes()) == sorted(rnx.nodes())
    for node in ("a", "b", "c"):
        assert sorted(rfx.successors(node)) == sorted(rnx.successors(node))
        assert sorted(rfx.predecessors(node)) == sorted(rnx.predecessors(node))
    with pytest.raises(nx.NetworkXError):
        rfx.add_node("nope")


@pytest.mark.parametrize("cls_name", CLASSES)
def test_instance_dict_identity_is_stable(cls_name):
    """`vars(self)` must return the same object across assignments.

    The removal argues that registering twice registered the SAME dict. If the
    instance dict could be swapped between the helper and the setattr, the two
    registrations would not be equivalent and the removal would be unsound.
    """
    graph = getattr(fnx, cls_name)()
    graph.add_edge("a", "b")
    before = vars(graph)
    graph._node = {"only": {}}
    assert vars(graph) is before, cls_name


@pytest.mark.parametrize("cls_name", ["DiGraph", "MultiDiGraph"])
def test_reverse_views_survive_a_gc_pass(cls_name):
    """Registration exists for GC lifetime; make a collection actually happen.

    A missed registration would not show up as a wrong answer, so this exercises
    the collector directly rather than only reading values back.
    """
    graph = getattr(fnx, cls_name)()
    for i in range(50):
        graph.add_edge(f"n{i}", f"n{(i + 1) % 50}")
    views = [graph.reverse(copy=False) for _ in range(20)]
    gc.collect()
    for view in views:
        assert view.number_of_nodes() == 50
        assert sorted(view.successors("n1")) == ["n0"]
    del views
    gc.collect()
    assert graph.number_of_nodes() == 50
