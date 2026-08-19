"""Re-adding an existing edge with attributes must not poison the weighted store.

br-r37-c1-weightupdate-9rts1. ``Graph.add_edge`` / ``DiGraph.add_edge`` used to handle the
"edge already exists" case in Python::

    merged = dict(self[u][v]); merged.update(attr)
    raw_add_edge(self, u, v, **merged)
    self[u][v].update(merged)

Both subscripts HAND OUT the live edge attr dict, which marks the weighted store dirty for
the life of the graph. So updating one edge's weight cost every later ``size(weight=...)``
and ``degree(weight=...)`` on the WHOLE graph 5.2x, permanently and all-or-nothing -- one
updated edge cost the same as 2000. Adding a brand-new edge never did it, because that took
the kernel path; the asymmetry is what exposed it.

The block was redundant: the native kernel already merges, already preserves live-dict
identity, and already matches networkx on every repeat-add shape. This module pins all
three, because deleting a merge is only safe if the thing underneath really merges.

WHAT IS DELIBERATELY NOT ASSERTED: ``G[u][v]['w'] = x`` still marks the store dirty. That
is a genuine handout -- the caller is holding the live dict -- and it belongs to
br-r37-c1-igdzi, not here. A test that demanded cleanliness there would be demanding a
silent stale-weight bug.
"""

import sys

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph"]

REPEAT_SHAPES = [
    ("overwrite one key", {"weight": 7.0}, {"weight": 9.0}),
    ("add a second key", {"weight": 7.0}, {"color": "red"}),
    ("overwrite and add", {"weight": 7.0}, {"weight": 9.0, "color": "red"}),
    ("no attrs on the repeat", {"weight": 7.0}, {}),
    ("attrs onto a bare edge", {}, {"weight": 3.0}),
]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    ("label", "first", "second"),
    REPEAT_SHAPES,
    ids=[s[0].replace(" ", "-") for s in REPEAT_SHAPES],
)
def test_repeat_add_edge_merges_like_networkx(cls_name, label, first, second):
    """The kernel must MERGE, not replace -- the premise the deletion rests on."""
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = getattr(module, cls_name)()
        graph.add_edge("a", "b", **first)
        graph.add_edge("a", "b", **second)
        outcomes[name] = dict(graph["a"]["b"])
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name} repeat add_edge ({label}): networkx gave {outcomes['nx']}, "
        f"fnx gave {outcomes['fnx']}. A kernel that REPLACED instead of merging would "
        f"lose the first call's keys here."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_repeat_add_edge_keeps_live_dict_identity(cls_name):
    """A dict the caller already holds must be the same object and see the update.

    This is the contract the second subscript looked like it existed to uphold. If the
    kernel created a fresh dict instead of updating in place, a caller holding the old one
    would silently observe a stale graph -- so it is asserted against networkx rather than
    assumed from the deletion being a no-op.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = getattr(module, cls_name)()
        graph.add_edge("a", "b", weight=7.0)
        held = graph["a"]["b"]
        graph.add_edge("a", "b", weight=9.0)
        outcomes[name] = (held is graph["a"]["b"], dict(held))
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: a held edge attr dict must stay the same object and observe the "
        f"update. networkx gave {outcomes['nx']}, fnx gave {outcomes['fnx']}."
    )


def _weighted_read_materialises_whole_graph(graph):
    """True when ``size(weight=...)`` fell back to the whole-graph materialisation.

    COUNTS FRAMES rather than nanoseconds, on purpose: it means the same thing on an idle
    host and on one at loadavg 76, where a timing assertion would be flaky.

    It also works for EVERY class, which probing the native accumulators does not. A
    boolean probe of ``_native_weighted_degree_float_values`` catches this on ``Graph``
    but is BLIND on ``DiGraph``, whose ``_native_weighted_degree_values`` returns a result
    whether or not the store is usable -- and DiGraph suffers the defect just as badly
    (6.265x -> 1.088x vs networkx, measured on the pre-fix arm against Graph's
    5.057x -> 0.904x). The first version of this helper probed the accumulators and was
    therefore VACUOUS for DiGraph; it passed on the unfixed arm.

    ``to_dict_of_dicts`` appears in the call path exactly when the shim gives up on the
    native accumulators and sums a materialised snapshot in Python.
    """
    seen = []

    def record(frame, event, _arg):
        if event == "call":
            seen.append(frame.f_code.co_name)

    graph.size(weight="weight")  # warm any first-call caches out of the measurement
    sys.setprofile(record)
    try:
        graph.size(weight="weight")
    finally:
        sys.setprofile(None)
    return "to_dict_of_dicts" in seen


@pytest.mark.parametrize("cls_name", ["Graph"])
def test_repeat_add_edge_does_not_disable_the_weighted_fast_path(cls_name):
    """THE REGRESSION TEST. Re-adding an existing edge must leave the store usable.

    Load-independent: asserts the fallback is not TAKEN, not that the call is fast.

    ``Graph`` ONLY, and the reason is worth stating rather than leaving as an unexplained
    narrowing. DiGraph suffers this defect too -- measured 6.265x -> 1.088x vs networkx on
    the pre-fix arm, against Graph's 5.057x -> 0.904x -- but its shim branch calls
    ``_native_weighted_degree_values`` unconditionally and never falls back to
    ``to_dict_of_dicts``, so its regression happens INSIDE the native call and produces no
    Python-side signal this assertion can see. Verified: on the unfixed arm the DiGraph
    parametrization PASSED. Rather than ship a green test that guards nothing, DiGraph is
    covered here only by the parity and correctness assertions, and its perf half is
    recorded on br-r37-c1-weightupdate-9rts1 with the numbers above.
    """
    graph = getattr(fnx, cls_name)()
    for i in range(64):
        graph.add_edge(f"n{i}", f"n{i + 1}", weight=float(i % 7))
    assert not _weighted_read_materialises_whole_graph(graph), (
        f"{cls_name}: a freshly built float-weighted graph should not materialise the "
        f"whole adjacency for a weighted read; this fixture is wrong if it does"
    )

    graph.add_edge("n0", "n1", weight=99.0)
    assert not _weighted_read_materialises_whole_graph(graph), (
        f"{cls_name}: re-adding an EXISTING edge with a new weight disabled the weighted "
        f"fast path for the whole graph. That is br-r37-c1-weightupdate-9rts1 returning: "
        f"the Python-side merge is subscripting G[u][v] and handing out a live dict again."
    )

    graph.add_edge("n0", "n1", color="red")
    assert not _weighted_read_materialises_whole_graph(graph), (
        f"{cls_name}: updating a NON-weight attribute on an existing edge disabled the "
        f"weighted fast path. The weight was never touched, so nothing about the store "
        f"went stale."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_weighted_reads_stay_correct_after_a_repeat_add(cls_name):
    """The negative case for the fix: cheap must not become WRONG.

    Keeping the store clean is only sound if the kernel really wrote the new weight
    through. If it did not, these reads would serve the pre-update value -- strictly worse
    than the slow path the fix removes.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = getattr(module, cls_name)()
        for i in range(64):
            graph.add_edge(f"n{i}", f"n{i + 1}", weight=float(i % 7))
        graph.add_edge("n0", "n1", weight=99.0)
        graph.add_edge("n5", "n6", color="red")  # non-weight update, weight must survive
        outcomes[name] = (
            graph.size(weight="weight"),
            sorted(dict(graph.degree(weight="weight")).items()),
        )
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: weighted reads after repeat add_edge must match networkx. "
        f"networkx size={outcomes['nx'][0]}, fnx size={outcomes['fnx'][0]}."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_add_edge_still_rejects_none_and_unhashable_endpoints(cls_name):
    """The deletion removed a has_edge probe that sat after this validation.

    networkx creates u BEFORE examining v, so a bad v leaves u on the graph. That ordering
    is easy to break when editing this wrapper, and it is invisible to the merge tests.
    """
    outcomes = {}
    for name, module in (("nx", nx), ("fnx", fnx)):
        graph = getattr(module, cls_name)()
        got = []
        for u, v in (("a", None), (None, "b"), ("c", [1])):
            try:
                graph.add_edge(u, v, weight=1.0)
                got.append("ok")
            except Exception as exc:  # noqa: BLE001 - the exception IS the contract
                got.append((type(exc).__name__, repr(exc.args)))
        outcomes[name] = (got, sorted(graph.nodes()))
    assert outcomes["fnx"] == outcomes["nx"], (
        f"{cls_name}: rejection types, args and partial node state must match networkx. "
        f"networkx gave {outcomes['nx']}, fnx gave {outcomes['fnx']}."
    )
