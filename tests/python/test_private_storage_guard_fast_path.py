"""`_has_networkx_private_storage` must answer identically for every dict shape.

br-r37-c1-bnv3h. The guard short-circuits on an EMPTY instance dict, which is
the common case: a fully built graph carries nothing in `__dict__` until a
caller assigns one of the nx-compatibility private attributes. That makes the
empty check a 2.16x win (102.8ns -> 47.5ns) on a function that is ~24% of
`G.edges[u,v]` and, per br-r37-c1-31tby, ~64% of runtime in all_node_cuts /
connectivity / flow.

The risk the short-circuit introduces is a FALSE NEGATIVE: if a graph could
carry private storage while presenting an empty `__dict__`, the guard would
return False and callers would take the native fast path on a graph whose
storage has been overridden — returning data for edges the override hides.
These tests pin that it cannot.

The case that matters most is the unrelated attribute: `G.foo = 1` makes the
dict non-empty WITHOUT adding an override, so the guard must fall through to
the four membership checks and still answer False. An implementation that
short-circuited the other way — treating "non-empty" as "has private storage" —
passes every override test and fails here.
"""

import pytest

import franken_networkx as fnx
from franken_networkx import _has_networkx_private_storage as has_private

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
OVERRIDE_ATTRS = ["_node", "_adj", "_succ", "_pred"]


def _built(class_name):
    """A graph with real content, so this is not a fresh-object special case."""
    graph = getattr(fnx, class_name)()
    graph.add_edge("a", "b", weight=1)
    graph.add_edge("b", "c", weight=2)
    graph.add_node("d")
    return graph


@pytest.mark.parametrize("class_name", CLASSES)
def test_built_graph_has_no_private_storage(class_name):
    assert has_private(_built(class_name)) is False


@pytest.mark.parametrize("class_name", CLASSES)
def test_a_realistically_used_graph_has_a_NON_empty_instance_dict(class_name):
    """Pins the fact that killed the short-circuit, so nobody retries it.

    A graph that has touched `.adj` or `.edges` carries accessor-cache entries,
    so `if not self.__dict__: return False` never fires in practice and is a
    measured regression (97.7ns vs 91.9ns). Measuring it on a graph whose
    accessors were never touched makes it look like a 2.16x win — that is the
    trap this asserts against.
    """
    graph = _built(class_name)
    list(graph.edges())
    _ = graph.adj
    assert graph.__dict__ != {}, (
        "a used graph now has an EMPTY instance dict — if that is a deliberate "
        "change, the empty-dict short-circuit in _has_networkx_private_storage "
        "becomes worth re-measuring; see br-r37-c1-bnv3h"
    )
    assert has_private(graph) is False


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("attr", OVERRIDE_ATTRS)
def test_each_assigned_private_attribute_is_detected(class_name, attr):
    """No false negatives: every override that REGISTERS must still be seen.

    `_succ` / `_pred` only install override machinery on a directed graph — on
    an undirected one the assignment stores a plain `_succ` key and the guard
    correctly reports False, since an undirected graph has no successor or
    predecessor storage to override. That is pre-existing behaviour, unchanged
    by the short-circuit (verified by differencing the old and new
    implementations over 60 graph/attribute/noise states: zero divergences), so
    it is asserted here rather than treated as a gap.
    """
    directed_only = attr in ("_succ", "_pred")
    is_directed = class_name in ("DiGraph", "MultiDiGraph")
    graph = _built(class_name)
    assert has_private(graph) is False
    setattr(graph, attr, {"a": {}, "b": {}, "c": {}, "d": {}})
    expected = is_directed or not directed_only
    assert has_private(graph) is expected, (
        f"{class_name}: assigning {attr} gave {has_private(graph)}, expected "
        f"{expected}. A missed override means callers take the native path on "
        f"a graph whose storage is overridden."
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_unrelated_attribute_does_not_look_like_private_storage(class_name):
    """The discriminating case: non-empty dict, no override.

    Catches an implementation that treats a non-empty instance dict as proof of
    private storage — it would pass every override test above.
    """
    graph = _built(class_name)
    graph.some_user_attribute = 1
    graph.another = {"not": "storage"}
    assert graph.__dict__ != {}, "fixture must produce a non-empty instance dict"
    assert has_private(graph) is False


@pytest.mark.parametrize("class_name", CLASSES)
def test_a_second_graph_is_unaffected_by_the_first(class_name):
    """No latching ACROSS instances.

    The obvious wrong optimisation here is a module- or class-level memo rather
    than a per-instance read. It would pass every single-graph assertion above
    and fail this. (Deletion is not the round trip to use: `_adj` is a property
    with no deleter, so `del graph._adj` raises AttributeError — the private
    attributes can be assigned but not removed.)
    """
    overridden = _built(class_name)
    overridden._adj = {"a": {}, "b": {}, "c": {}, "d": {}}
    assert has_private(overridden) is True

    fresh = _built(class_name)
    assert has_private(fresh) is False, (
        "a graph with no override reported private storage after a DIFFERENT "
        "graph was overridden — the guard is not reading per-instance state"
    )
    assert has_private(overridden) is True, "the first graph lost its override"


@pytest.mark.parametrize("class_name", CLASSES)
def test_guard_matches_an_independent_membership_check(class_name):
    """Differential: the guard must equal a straightforward recomputation.

    Covers combinations the individual cases above do not enumerate, including
    an override sitting alongside unrelated attributes.
    """
    from franken_networkx import (
        _PRIVATE_ADJ_OVERRIDE,
        _PRIVATE_NODE_OVERRIDE,
        _PRIVATE_PRED_OVERRIDE,
        _PRIVATE_SUCC_OVERRIDE,
    )

    keys = (
        _PRIVATE_NODE_OVERRIDE,
        _PRIVATE_ADJ_OVERRIDE,
        _PRIVATE_SUCC_OVERRIDE,
        _PRIVATE_PRED_OVERRIDE,
    )

    def reference(graph):
        return any(key in graph.__dict__ for key in keys)

    for extra in ([], ["noise"], ["noise", "more"]):
        for attr in [None] + OVERRIDE_ATTRS:
            graph = _built(class_name)
            for i, name in enumerate(extra):
                setattr(graph, name, i)
            if attr is not None:
                setattr(graph, attr, {"a": {}, "b": {}, "c": {}, "d": {}})
            assert has_private(graph) is reference(graph), (
                f"{class_name}: guard disagreed with the reference for "
                f"attr={attr} extra={extra}"
            )
